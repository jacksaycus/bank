import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import any_, desc, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.auth.models import User
from backend.app.auth.utils import generate_otp
from backend.app.bank_account.enums import AccountStatusEnum
from backend.app.bank_account.models import BankAccount
from backend.app.bank_account.utils import calculate_conversion
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.core.services.transfer_alert import send_transfer_alert
from backend.app.core.tasks.statement import generate_statement_pdf
from backend.app.transaction.enums import (
    TransactionCategoryEnum,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from backend.app.transaction.models import Transaction
from backend.app.transaction.utils import (
    TransactionFailureReason,
    mark_transaction_failed,
)

logger = get_logger()


async def process_deposit(
    *,
    amount: Decimal,
    account_id: uuid.UUID,
    teller_id: uuid.UUID,
    description: str,
    session: AsyncSession,
) -> tuple[Transaction, BankAccount, User]:
    try:
        statement = (
            select(BankAccount, User).join(User).where(BankAccount.id == account_id)
        )
        result = await session.exec(statement)
        account_user = result.first()

        if not account_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Account not found"},
            )

        account, account_owner = account_user

        if account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Account is not active"},
            )
        reference = f"DEP{uuid.uuid4().hex[:8].upper()}"

        balance_before = Decimal(str(account.balance))
        balance_after = balance_before + amount

        transaction = Transaction(
            amount=amount,
            description=description,
            reference=reference,
            transaction_type=TransactionTypeEnum.Deposit,
            transaction_category=TransactionCategoryEnum.Credit,
            status=TransactionStatusEnum.Pending,
            balance_before=balance_before,
            balance_after=balance_after,
            receiver_account_id=account_id,
            receiver_id=account_owner.id,
            processed_by=teller_id,
            transaction_metadata={
                "currency": account.currency,
                "account_number": account.account_number,
            },
        )
        teller = await session.get(User, teller_id)

        if teller:
            if transaction.transaction_metadata is None:
                transaction.transaction_metadata = {}
            transaction.transaction_metadata["teller_name"] = teller.full_name

            transaction.transaction_metadata["teller_email"] = teller.email

        account.balance = float(balance_after)

        transaction.status = TransactionStatusEnum.Completed
        transaction.completed_at = datetime.now(timezone.utc)

        session.add(transaction)
        session.add(account)
        await session.commit()

        await session.refresh(transaction)
        await session.refresh(account)

        return transaction, account, account_owner

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to process deposit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to process deposit"},
        )


async def initiate_transfer(
    *,
    sender_id: uuid.UUID,
    sender_account_id: uuid.UUID,
    receiver_account_number: str,
    amount: Decimal,
    description: str,
    security_answer: str,
    session: AsyncSession,
) -> tuple[Transaction, BankAccount, BankAccount, User, User]:

    try:
        reciever_account_result = await session.exec(
            select(BankAccount).where(
                BankAccount.account_number == receiver_account_number,
                BankAccount.user_id == sender_id,
            )
        )
        receiver_account = reciever_account_result.first()

        if receiver_account:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Cannot transfer to your own account",
                    "action": "Please use a different recipient account",
                },
            )

        sender_stmt = (
            select(BankAccount, User)
            .join(User)
            .where(
                BankAccount.id == sender_account_id, BankAccount.user_id == sender_id
            )
        )

        sender_result = await session.exec(sender_stmt)
        sender_data = sender_result.first()

        if not sender_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Sender account not found"},
            )

        sender_account, sender = sender_data

        if sender_account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Sender account is not active"},
            )

        if security_answer != sender.security_answer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "Incorrect security answer"},
            )

        receiver_stmt = (
            select(BankAccount, User)
            .join(User)
            .where(BankAccount.account_number == receiver_account_number)
        )
        receiver_result = await session.exec(receiver_stmt)
        receiver_data = receiver_result.first()

        if not receiver_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Receiver account not found"},
            )

        receiver_account, receiver = receiver_data

        if receiver_account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Receiver account is not active"},
            )

        if Decimal(str(sender_account.balance)) < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Insuffienct balance"},
            )

        try:
            if sender_account.currency != receiver_account.currency:
                converted_amount, exchange_rate, conversion_fee = calculate_conversion(
                    amount, sender_account.currency, receiver_account.currency
                )
            else:
                converted_amount = amount
                exchange_rate = Decimal("1.0")
                conversion_fee = Decimal("0")

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": f"Currency conversion failed: {str(e)}",
                },
            )

        reference = f"TRF{uuid.uuid4().hex[:8].upper()}"

        transaction = Transaction(
            amount=amount,
            description=description,
            reference=reference,
            transaction_type=TransactionTypeEnum.Transfer,
            transaction_category=TransactionCategoryEnum.Debit,
            status=TransactionStatusEnum.Pending,
            balance_before=Decimal(str(sender_account.balance)),
            balance_after=Decimal(str(sender_account.balance)) - amount,
            sender_account_id=sender_account.id,
            receiver_account_id=receiver_account.id,
            sender_id=sender.id,
            receiver_id=receiver.id,
            transaction_metadata={
                "conversion_rate": str(exchange_rate),
                "conversion_fee": str(conversion_fee),
                "original_amount": str(amount),
                "converted_amount": str(converted_amount),
                "from_currency": sender_account.currency.value,
                "to_currency": receiver_account.currency.value,
            },
        )
        session.add(transaction)
        await session.commit()
        await session.refresh(transaction)

        otp = generate_otp()

        sender.otp = otp
        sender.otp_expiry_time = datetime.now(timezone.utc) + timedelta(
            minutes=settings.OTP_EXPIRATION_MINUTES
        )

        session.add(transaction)
        session.add(sender)
        await session.commit()
        await session.refresh(transaction)

        return transaction, sender_account, receiver_account, sender, receiver
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to initiate transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to initiate transfer"},
        )


async def complete_transfer(
    *, reference: str, otp: str, session: AsyncSession
) -> tuple[Transaction, BankAccount, BankAccount, User, User]:
    try:
        stmt = select(Transaction).where(
            Transaction.reference == reference,
            Transaction.status == TransactionStatusEnum.Pending,
        )
        result = await session.exec(stmt)
        transaction = result.first()

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Transfer not found"},
            )

        sender_account = await session.get(BankAccount, transaction.sender_account_id)
        receiver_account = await session.get(
            BankAccount, transaction.receiver_account_id
        )
        sender = await session.get(User, transaction.sender_id)
        receiver = await session.get(User, transaction.receiver_id)

        if not all([sender_account, receiver_account, sender, receiver]):
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.INVALID_ACCOUNT,
                details={
                    "sender_account_found": bool(sender_account),
                    "receiver_account_found": bool(receiver_account),
                    "sender_found": bool(sender),
                    "receiver_found": bool(receiver),
                },
                session=session,
                error_message="Account information not found",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Account information not found"},
            )

        if not sender or not sender.otp or sender.otp != otp:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.INVALID_OTP,
                details={"provided_otp": otp},
                session=session,
                error_message="Invalid OTP",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "Invalid OTP"},
            )

        if (
            not sender.otp_expiry_time
            or datetime.now(timezone.utc) > sender.otp_expiry_time
        ):
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.OTP_EXPIRED,
                details={
                    "expiry_time": (
                        sender.otp_expiry_time.isoformat()
                        if sender.otp_expiry_time
                        else None
                    ),
                    "current_time": datetime.now(timezone.utc).isoformat(),
                },
                session=session,
                error_message="OTP has expired",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"status": "error", "message": "OTP has expired"},
            )

        if sender_account and sender_account.account_status != AccountStatusEnum.Active:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.ACCOUNT_INACTIVE,
                details={"account": "sender"},
                session=session,
                error_message="Sender account is no longer active",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Sender account is no longer active",
                },
            )

        if (
            receiver_account
            and receiver_account.account_status != AccountStatusEnum.Active
        ):
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.ACCOUNT_INACTIVE,
                details={"account": "receiver"},
                session=session,
                error_message="Receiver account is no longer active",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "Receiver account is no longer active",
                },
            )
        if not sender_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Sendwer account not found"},
            )

        if Decimal(str(sender_account.balance)) < transaction.amount:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.INSUFFICIENT_BALANCE,
                details={
                    "required_amount": str(transaction.amount),
                    "available_balance": str(sender_account.balance),
                    "shortfall": str(
                        transaction.amount - Decimal(str(sender_account.balance))
                    ),
                },
                session=session,
                error_message="Insufficient balance",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Insufficient balance"},
            )

        if not transaction.transaction_metadata:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.SYSTEM_ERROR,
                details={"error": "Missing transaction metadata"},
                session=session,
                error_message="System error: Missing transaction metadata",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "System error: Missing transaction metadata",
                },
            )

        if not transaction.transaction_metadata:
            raise ValueError("Transaction metadata is missing")

        converted_amount = Decimal(transaction.transaction_metadata["converted_amount"])

        sender_account.balance = float(
            Decimal(str(sender_account.balance)) - transaction.amount
        )

        if not receiver_account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Receiver account not found"},
            )

        receiver_account.balance = float(
            Decimal(str(receiver_account.balance)) + converted_amount
        )

        transaction.status = TransactionStatusEnum.Completed
        transaction.completed_at = datetime.now(timezone.utc)

        sender.otp = ""
        sender.otp_expiry_time = None

        session.add(transaction)
        session.add(sender_account)
        session.add(receiver_account)
        session.add(sender)
        await session.commit()

        await session.refresh(transaction)
        await session.refresh(sender_account)
        await session.refresh(receiver_account)
        await session.refresh(sender)
        await session.refresh(receiver)

        if not receiver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Receiver not found"},
            )
        return transaction, sender_account, receiver_account, sender, receiver

    except HTTPException:
        await session.rollback()
        raise

    except Exception as e:
        if transaction:
            await mark_transaction_failed(
                transaction=transaction,
                reason=TransactionFailureReason.SYSTEM_ERROR,
                details={"error": str(e)},
                session=session,
                error_message="A system error occurred",
            )
        await session.rollback()
        logger.error(f"Failed to complete transfer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to complete the transfer"},
        )


async def process_withdrawal(
    *,
    account_number: str,
    amount: Decimal,
    username: str,
    description: str,
    session: AsyncSession,
) -> tuple[Transaction, BankAccount, User]:
    try:
        statement = (
            select(BankAccount, User)
            .join(User)
            .where(
                BankAccount.account_number == account_number, User.username == username
            )
        )
        result = await session.exec(statement)
        account_user = result.first()

        if not account_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message": "Account or username not found"},
            )

        account, user = account_user

        if account.account_status != AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Account is not active"},
            )

        if Decimal(str(account.balance)) < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status": "error", "message": "Insufficient balance"},
            )

        reference = f"WTH{uuid.uuid4().hex[:8].upper()}"

        balance_before = Decimal(str(account.balance))
        balance_after = balance_before - amount

        transaction = Transaction(
            amount=amount,
            description=description,
            reference=reference,
            transaction_type=TransactionTypeEnum.Withdrawal,
            transaction_category=TransactionCategoryEnum.Debit,
            status=TransactionStatusEnum.Completed,
            balance_before=balance_before,
            balance_after=balance_after,
            sender_account_id=account.id,
            sender_id=user.id,
            completed_at=datetime.now(timezone.utc),
            transaction_metadata={
                "currency": account.currency.value,
                "account_number": account.account_number,
                "withdrawal_method": "cash",
            },
        )

        session.add(transaction)
        await session.commit()
        await session.refresh(transaction)

        transaction.status = TransactionStatusEnum.Completed
        transaction.completed_at = datetime.now(timezone.utc)

        account.balance = float(balance_after)

        session.add(account)
        await session.commit()

        await session.refresh(account)

        return transaction, account, user
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to process withdrawal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to process withdrawal"},
        )


async def get_user_transactions(
    user_id: uuid.UUID,
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    transaction_type: TransactionTypeEnum | None = None,
    transaction_category: TransactionCategoryEnum | None = None,
    transaction_status: TransactionStatusEnum | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
) -> tuple[list[Transaction], int]:
    try:
        account_stmt = select(BankAccount.id).where(BankAccount.user_id == user_id)
        result = await session.exec(account_stmt)
        account_ids = [account_id for account_id in result.all()]

        if not account_ids:
            return [], 0

        base_query = select(Transaction).where(
            or_(
                Transaction.sender_id == user_id,
                Transaction.receiver_id == user_id,
                Transaction.sender_account_id == any_(account_ids),
                Transaction.receiver_account_id == any_(account_ids),
            )
        )
        if start_date:
            base_query = base_query.where(Transaction.created_at >= start_date)

        if end_date:
            base_query = base_query.where(Transaction.created_at <= end_date)

        if transaction_type:
            base_query = base_query.where(
                Transaction.transaction_type == transaction_type
            )

        if transaction_category:
            base_query = base_query.where(
                Transaction.transaction_category == transaction_category
            )
        if transaction_status:
            base_query = base_query.where(Transaction.status == transaction_status)

        if min_amount is not None:
            base_query = base_query.where(Transaction.amount >= min_amount)
        if max_amount is not None:
            base_query = base_query.where(Transaction.amount <= max_amount)

        base_query = base_query.order_by(desc(Transaction.created_at))

        count_query = select(func.count()).select_from(base_query.subquery())
        total = await session.exec(count_query)
        total_count = total.first() or 0

        transactions = await session.exec(base_query.offset(skip).limit(limit))

        transaction_list = list(transactions.all())

        for transaction in transaction_list:
            await session.refresh(
                transaction,
                ["sender", "receiver", "sender_account", "receiver_account"],
            )

            if not transaction.transaction_metadata:
                transaction.transaction_metadata = {}

            if transaction.sender_id == user_id:
                if transaction.receiver:
                    transaction.transaction_metadata["counterparty_name"] = (
                        transaction.receiver.full_name
                    )

                if transaction.receiver_account:
                    transaction.transaction_metadata["counterparty_account"] = (
                        transaction.receiver_account.account_number
                    )
            else:
                if transaction.sender:
                    transaction.transaction_metadata["counterparty_name"] = (
                        transaction.sender.full_name
                    )
                if transaction.sender_account:
                    transaction.transaction_metadata["counterparty_account"] = (
                        transaction.sender_account.account_number
                    )

        return transaction_list, total_count
    except Exception as e:
        logger.error(f"Error fetching user transactions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to fetch transaction history",
                "action": "Please try again later",
            },
        )


async def get_user_statement_data(
    user_id: uuid.UUID,
    start_date: datetime,
    end_date: datetime,
    session: AsyncSession,
) -> tuple[dict[str, Any], list[Transaction]]:
    try:
        user_stmt = select(User).where(User.id == user_id)
        result = await session.exec(user_stmt)
        user = result.first()

        if not user:
            raise ValueError(f"User {user_id} not found")

        full_name = f"{user.first_name} {user.middle_name + ' ' if user.middle_name else ''}{user.last_name}".title().strip()

        user_info = {
            "username": user.username,
            "email": user.email,
            "full_name": full_name,
        }

        txn_stmt = (
            select(Transaction)
            .where(
                (Transaction.sender_id == user_id)
                | (Transaction.receiver_id == user_id),
                Transaction.created_at >= start_date,
                Transaction.created_at <= end_date,
            )
            .order_by(desc(Transaction.created_at))
        )

        txn_result = await session.exec(txn_stmt)
        transactions = txn_result.all()

        return user_info, list(transactions)

    except Exception as e:
        logger.error(f"Failed to get statement data for user {user_id}: {e}")
        raise


async def prepare_statement_data(
    user_id: uuid.UUID,
    start_date: datetime,
    end_date: datetime,
    session: AsyncSession,
    account_number: str | None = None,
) -> dict:

    try:
        user_query = select(User).where(User.id == user_id)
        result = await session.exec(user_query)
        user = result.first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        if account_number:
            account_query = select(BankAccount).where(
                BankAccount.account_number == account_number,
                BankAccount.user_id == user_id,
            )

            account_result = await session.exec(account_query)
            account = account_result.first()

            if not account:
                raise ValueError("Account not found or does not belong to user")

            accounts = [account]
        else:
            accounts_query = select(BankAccount).where(BankAccount.user_id == user_id)
            accounts_result = await session.exec(accounts_query)
            accounts = accounts_result.all()

        account_details = []

        for acc in accounts:
            if acc.account_number:
                account_details.append(
                    {
                        "account_number": acc.account_number,
                        "account_name": acc.account_name,
                        "account_type": acc.account_type.value,
                        "currency": acc.currency.value,
                        "balance": str(acc.balance),
                    }
                )
        account_ids = [acc.id for acc in accounts]

        transactions_query = (
            select(Transaction)
            .where(
                or_(
                    Transaction.sender_account_id == any_(account_ids),
                    Transaction.receiver_account_id == any_(account_ids),
                ),
                Transaction.created_at >= start_date,
                Transaction.created_at <= end_date,
                Transaction.status == TransactionStatusEnum.Completed,
            )
            .order_by(desc(Transaction.created_at))
        )

        result = await session.exec(transactions_query)
        transactions = result.all()

        user_data = {
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": f"{user.first_name} {user.middle_name + ' ' if user.middle_name else ''}{user.last_name}".strip(),
            "accounts": account_details,
        }

        transaction_data = []
        for txn in transactions:
            sender_account = (
                await session.get(BankAccount, txn.sender_account_id)
                if txn.sender_account_id
                else None
            )
            receiver_account = (
                await session.get(BankAccount, txn.receiver_account_id)
                if txn.receiver_account_id
                else None
            )

            transaction_data.append(
                {
                    "reference": txn.reference,
                    "amount": str(txn.amount),
                    "description": txn.description,
                    "created_at": txn.created_at.strftime("%Y-%m-%d"),
                    "transaction_type": txn.transaction_type.value,
                    "transaction_category": txn.transaction_category.value,
                    "balance_after": str(txn.balance_after),
                    "sender_account": (
                        sender_account.account_number if sender_account else None
                    ),
                    "receiver_account": (
                        receiver_account.account_number if receiver_account else None
                    ),
                    "metadata": txn.transaction_metadata,
                }
            )
        return {
            "user": user_data,
            "transactions": transaction_data,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "is_single_account": bool(account_number),
        }
    except ValueError as e:
        logger.error(f"Error preparing statement data: {e}")
        raise
    except Exception as e:
        logger.error(f"Error Preparing statement data: {e}")
        raise


async def _complete_approved_transfer(transaction: Transaction, session: AsyncSession):
    try:
        sender = await session.get(User, transaction.sender_id)

        receiver = await session.get(User, transaction.receiver_id)

        sender_account = await session.get(BankAccount, transaction.sender_account_id)

        receiver_account = await session.get(
            BankAccount, transaction.receiver_account_id
        )

        if not sender:
            raise ValueError("Sender not found")
        if not receiver:
            raise ValueError("Receiver not found")
        if not sender_account:
            raise ValueError("Sender account not found")
        if not receiver_account:
            raise ValueError("Receiver account not found")

        if not transaction.transaction_metadata:
            raise ValueError("Transaction metadata is missing")

        converted_amount_str = transaction.transaction_metadata.get("converted_amount")

        if not converted_amount_str:
            raise ValueError("Converted amount is missing from metadata")

        try:
            converted_amount = Decimal(converted_amount_str)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid converted amount format:{converted_amount_str}")

        current_sender_balance = Decimal(str(sender_account.balance))

        if current_sender_balance < transaction.amount:
            raise ValueError("Insufficient balance for transfer")

        try:
            sender_account.balance = float(current_sender_balance - transaction.amount)

            receiver_account.balance = float(
                Decimal(str(receiver_account.balance)) + converted_amount
            )

            transaction.status = TransactionStatusEnum.Completed
            transaction.completed_at = datetime.now(timezone.utc)

            session.add(sender_account)
            session.add(receiver_account)
            session.add(transaction)

            await session.commit()

            await session.refresh(transaction)
            await session.refresh(sender_account)
            await session.refresh(receiver_account)

            try:
                await send_transfer_alert(
                    sender_email=sender.email,
                    receiver_email=receiver.email,
                    sender_name=sender.full_name,
                    receiver_name=receiver.full_name,
                    sender_account_number=sender_account.account_number or "Uknown",
                    receiver_account_number=receiver_account.account_number
                    or "Unknown",
                    amount=transaction.amount,
                    converted_amount=converted_amount,
                    sender_currency=sender_account.currency,
                    receiver_currency=receiver_account.currency,
                    exchange_rate=Decimal(
                        transaction.transaction_metadata.get("conversion_rate", "1"),
                    ),
                    conversion_fee=Decimal(
                        transaction.transaction_metadata.get("conversion_fee", "0"),
                    ),
                    description=transaction.description,
                    reference=transaction.reference,
                    transaction_date=transaction.completed_at or transaction.created_at,
                    sender_balance=Decimal(str(sender_account.balance)),
                    receiver_balance=Decimal(str(receiver_account.balance)),
                )
                logger.info(
                    f"Successfully sent transfer approval notificatoin for transaction {transaction.reference}"
                )
            except Exception as e:
                logger.error(f"Failed to send transfer approval notification: {e}")
        except Exception as e:
            await session.rollback()
            raise ValueError(f"Failed to process transfer: {str(e)}")

    except ValueError as e:
        await session.rollback()
        logger.error(f"Validation error in _complete_approved_transfer: {e}")

        transaction.status = TransactionStatusEnum.Failed
        transaction.transaction_metadata = {
            **(transaction.transaction_metadata or {}),
            "failure_reason": str(e),
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        session.add(transaction)
        await session.commit()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error in _complete_approved_transfer: {e}")
        raise

async def generate_user_statement(
        user_id: uuid.UUID,
        start_date: datetime,
        end_date: datetime,
        session: AsyncSession,
        account_number: str | None = None,
) -> dict:
    try:
        statement_data = await prepare_statement_data(
            user_id = user_id,
            start_date = start_date,
            end_date = end_date,
            session = session,
            account_number=account_number,
        )

        statement_id = str(uuid.uuid4())

        task = generate_statement_pdf.delay(
            statement_data = statement_data, statement_id=statement_id
        )

        return {
            "status": "pending",
            "message" : "Statement generation initiated",
            "statement_id": statement_id,
            "task_id": task.id
        }
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status":"error","message":str(e)},
        )
    except Exception as e:
        logger.error(f"failed to initiate statement generation: {e}")
        raise

    