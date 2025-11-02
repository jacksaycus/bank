from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.auth.models import User
from backend.app.bank_account.enums import AccountStatusEnum
from backend.app.bank_account.models import BankAccount
from backend.app.bank_account.schema import BankAccountCreateSchema
from backend.app.bank_account.utils import generate_account_number
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger()

async def get_primary_bank_account(
        user_id: UUID, session: AsyncSession
) -> BankAccount | None:
    
    statement = select(BankAccount).where(
        BankAccount.user_id == user_id, BankAccount.is_primary
    )
    result = await session.exec(statement)
    return result.first()

async def validate_user_kyc(user: User) -> bool:
    if not user.profile:
        return False
    if not user.next_of_kins or len(user.next_of_kins) == 0:
        return False
    return True

async def create_bank_account(
        user_id: UUID, account_data: BankAccountCreateSchema, session: AsyncSession
) -> BankAccount:
    try:
        statement = select(User).where(User.id == user_id)
        result = await session.exec(statement)
        user = result.first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status":"error", "message":"User not found"},
            )
        
        await session.refresh(user, ["profile", "next_of_kins"])

        if not await validate_user_kyc(user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "KYC requirements not met",
                    "action": "Please complete your profile and add at least one next of kin",
                },
            )
        
        statement = select(BankAccount).where(BankAccount.user_id == user_id)
        result = await session.exec(statement)
        existing_accounts = result.all()
        if len(existing_accounts) >= settings.MAX_BANK_ACCOUNTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message" : "Maximum number of accounts reached",
                },
            )
        if account_data.is_primary:
            primary_exists = any(account.is_primary for account in existing_accounts)

            if primary_exists:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "A primary account already exists",
                        "action": "Please unset the existing primary account first",
                    },
                )
        elif len(existing_accounts) == 0:
            account_data.is_primary = True

        account_number = generate_account_number(account_data.currency)
        new_account = BankAccount(
            **account_data.model_dump(exclude={"account_number"}),
            user_id = user_id,
            account_number=account_number,
        )

        session.add(new_account)

        await session.commit()
        await session.refresh(new_account)

        return new_account
    
    except HTTPException as e:
        await session.rollback()
        logger.error(f"Failed to create account: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error","message":"Failed to create account"},
        )
    
async def activate_bank_account(
    account_id: UUID,
    verified_by: UUID,
    session: AsyncSession,
) -> tuple[BankAccount, User]:
    try:
        statement = (
            select(BankAccount, User)
            .join(User)
            .where(BankAccount.id == account_id, BankAccount.user_id == verified_by)
        )
        logger.debug(
            f"verified_by {verified_by} {statement} "
        )
        

        result = await session.exec(statement)
        
        account_user_tuple = result.first()
        logger.info(f"result is {account_user_tuple} ")

        if not account_user_tuple:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"status": "error", "message":"Bank account not found"},
            )
        
        account, user = account_user_tuple

        if account.account_status == AccountStatusEnum.Active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"status":"error", "message": "Account is already activated"},
            )
        
        account.kyc_submitted = True
        account.kyc_verified = True
        account.kyc_verified_on = datetime.now(timezone.utc)
        account.kyc_verified_by = verified_by
        account.account_status = AccountStatusEnum.Active

        session.add(account)
        await session.commit()
        await session.refresh(account)

        return account, user
    
    except HTTPException as http_ex:
        await session.rollback()
        raise http_ex
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to activate bank account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error","message":"Failed to activate bank account"}
        )
    