from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.bank_account import activate_bank_account
from backend.app.auth.schema import RoleChoicesSchema
from backend.app.bank_account.schema import BankAccountReadSchema
from backend.app.core.db import get_session
from backend.app.core.db import get_logger
from backend.app.core.services.bank_account_activated_email import (
    send_account_activated_email,
)

logger = get_logger()

router = APIRouter(prefix="/bank-account")

@router.patch(
    "/{account_id}/activate",
    response_model=BankAccountReadSchema,
    status_code=status.HTTP_200_OK,
    description="Activate a bank account after KYC verification. Only accessible to account executives",
)
async def activate_account(
    account_id: UUID,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> BankAccountReadSchema:
    try:
        if not current_user.role == RoleChoicesSchema.ACCOUNT_EXECUTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status" : "error",
                    "message" : "Only account executives can activate bank accounts",
                },
            )
        activated_account, account_owner = await activate_bank_account(
            account_id=account_id, verified_by=current_user.id, session=session
        )
        try:
            if not activated_account.account_number:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"status": "error", "message":"Account number not found"},
                )
            await send_account_activated_email(
                email=account_owner.email,
                full_name=account_owner.full_name,
                account_number=activated_account.account_number,
                account_name=activated_account.account_name,
                account_type=activated_account.account_type.value,
                currency=activated_account.currency.value,
            )
            logger.info(f"Bank Account activated email sent to {account_owner.email}")
        except Exception as email_error:
            logger.error(f"Failed to send bank account activated email: {email_error}")

        logger.info(
            f"Bank account {account_id} activated by account executinve {current_user.email}"
        )

        return BankAccountReadSchema.model_validate(activated_account)

    except HTTPException as http_ex:
        raise http_ex

    except Exception as e:
        logger.error(f"Failed to activate bank account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status":"error","message":"Failed to active bank account"},
        )