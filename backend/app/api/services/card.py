import uuid
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.auth.models import User
from backend.app.auth.schema import RoleChoicesSchema
from backend.app.bank_account.enums import AccountStatusEnum
from backend.app.bank_account.models import BankAccount
from backend.app.core.logging import get_logger
from backend.app.transaction.enums import (
    TransactionCategoryEnum,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from backend.app.transaction.models import Transaction
from backend.app.virtual_card.enums import VirtualCardStatusEnum
from backend.app.virtual_card.models import VirtualCard
from backend.app.virtual_card.utils import (
    generate_card_expiry_date,
    generate_cvv,
    generate_visa_card_number,
)   

logger = get_logger()

async def created_virtual_card(
        user_id: UUID, bank_account_id: UUID, card_data: dict, session: AsyncSession
) -> tuple[VirtualCard, User, BankAccount ]:
    try:
        statement = (
            select(BankAccount, User)
            .join(User)
            .where(BankAccount.id == bank_account_id, BankAccount.user_id == user_id)
        )
        result = await session.exec(statement)
        account_user = result.first()

        if not account_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message" : "Bank account not found or does not belong to the user",
                },
            )
        
        bank_account, user = account_user

        if bank_account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Bank accountis not active"},
            )
        
        card_currency = card_data.get("currency")

        if card_currency != bank_account.currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message" : "Card currency must match the bank account currency",
                },
            )
        
        cleaned_data = card_data.copy()

        cleaned_data.pop("card_number", None)
        cleaned_data.pop("card_status", None)
        cleaned_data.pop("is_active", None)
        cleaned_data.pop("cvv_hash", None)
        cleaned_data.pop("total_topped_up", None)
        cleaned_data.pop("card_metadata", None)

        card_number = generate_visa_card_number()

        if not cleaned_data.get("expiry_date"):
            expiry_date = generate_card_expiry_date()
            cleaned_data["expiry_date"] = expiry_date.date()

        card = VirtualCard(
            **cleaned_data,
            card_number=card_number,
            bank_account_id=bank_account_id,
            card_status=VirtualCardStatusEnum.Pending,
            is_active=True,
            available_balance=0.0,
            total_topped_up=0.0,
            last_top_up_date=datetime.now(timezone.utc),
            card_metadata={
                "created_by": str(user.id),
                 "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        
        session.add(card)
        await session.commit()

        await session.refresh(card)

        return card, user, bank_account
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to create virtual card: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message" : "Failed to create virtual card"},
        )

async def block_virtual_card(
    card_id: UUID, block_data: dict, blocked_by: UUID, session: AsyncSession
) -> tuple[VirtualCard, User]:

    try:
        statement = (
            select(VirtualCard, User)
            .select_from(VirtualCard)
            .join(BankAccount)
            .join(User)
            .where(VirtualCard.id == card_id)
        )
        result = await session.exec(statement)
        card_data = result.first()

        if not card_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Virtual card not found"},
            )
        
        card, card_owner = card_data

        if card.card_status ==  VirtualCardStatusEnum.Blocked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status":"error","message":"Card is already blocked"},
            )
        
        block_time = datetime.now(timezone.utc)
        card.card_status =  VirtualCardStatusEnum.Blocked
        card.block_reason = block_data["block_reason"]
        card.block_reason_description = block_data["block_reason_description"]
        card.blocked_by = blocked_by
        card.blocked_at = block_time
        if not card.card_metadata:
            card.card_metadata = {}

        card.card_metadata.update(
            {
                "blocked_at": block_time.isoformat(),
                "blocked_by": str(blocked_by),
                "block_reason" : block_data["block_reason"].value,
            }
        )

        session.add(card)

        await session.commit()

        await session.refresh(card)

        return card, card_owner
    
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to block virtual card: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to block virtual card"},
        )

async def top_up_virtual_card(
    card_id: UUID,
    account_number: str,
    amount: float,
    description: str,
    session: AsyncSession,
) -> tuple[VirtualCard, Transaction]:
    try:
        statement = (
            select(VirtualCard, BankAccount)
            .join(BankAccount)
            .where(
                VirtualCard.id == card_id, BankAccount.account_number == account_number
            )
        )
        result = await session.exec(statement)
        card_account = result.first()

        if not card_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "satus": "error",
                    "message" : "Virtual card or bank account not found",
                },
            )
        
        card, bank_account = card_account

        if card.card_status != VirtualCardStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"satus": "error", "message": "card is not active"},
            )
        
        if Decimal(str(bank_account.balance)) < Decimal(str(amount)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message" : "Insufficient balance in bank account",
                },
            )
        
        if card.currency != bank_account.currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Currency mismatch between card and bank account",
                },
            )
        
        reference = f"TOPUP{uuid.uuid4().hex[:8].upper()}"

        balance_before = Decimal(str(bank_account.balance))
        balance_after = balance_before = Decimal(str(amount))

        current_time = datetime.now(timezone.utc)

        transaction = Transaction(
            amount=Decimal(str(amount)),
            description=description,
            reference=reference,
            transaction_type=TransactionTypeEnum.Transfer,
            transaction_category=TransactionCategoryEnum.Debit,
            status=TransactionStatusEnum.Completed,
            balance_before=balance_before,
            balance_after=balance_after,
            sender_account_id=bank_account.id,
            completed_at=current_time,
            transaction_metadata={
                "top_up_type": "virtual_card",
                "card_id": str(card.id),
                "card_last_four": card.last_four_digits,
                "currency": card.currency.value,
            },
        )
        
        bank_account.balance = float(balance_after)
        card.available_balance += amount
        card.total_topped_up += amount

        card.last_top_up_date = current_time

        session.add(transaction)
        session.add(bank_account)
        session.add(card)
        await session.commit()

        await session.refresh(transaction)
        await session.refresh(card)

        return card, transaction
    
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to top up virtual card: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to process card top-up"},
        )
