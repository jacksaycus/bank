from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.transaction import process_deposit
from backend.app.auth.schema import RoleChoicesSchema
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.services.deposit_alert import send_deposit_alert
from backend.app.transaction.enums import TransactionTypeEnum
from backend.app.transaction.schema import DepositRequestSchema

logger = get_logger()

router =APIRouter(prefix="/bank-account")

@router.post("/deposit", status_code=status.HTTP_201_CREATED)
async def carete_deposit(
    deposit_data: DepositRequestSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    
    if not current_user.role == RoleChoicesSchema.TELLER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "message": "Only tellers can process deposits"},
        )
    try:
        transaction, account, account_owner = await process_deposit(
            amount=deposit_data.amount,
            account_id=deposit_data.account_id,
            teller_id=current_user.id,
            description=deposit_data.description,
            session=session,
        )

        if not account.account_number:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status":"error","message":"Account number is required"},
            )
        
        try:
            currency_value = account.currency.value
            await send_deposit_alert(
                email=account_owner.email,
                full_name=account_owner.full_name,
                action=TransactionTypeEnum.Deposit.value,
                amount=transaction.amount,
                account_name=account.account_name,
                account_number=account.account_number,
                currency=currency_value,
                description=transaction.description,
                transaction_date=transaction.completed_at or transaction.created_at,
                reference=transaction.reference,
                balance=transaction.balance_after
            )
        except Exception as email_error:
            logger.error(f"Failed to send transaction alert: {email_error}")

        return {
            "status": "success",
            "message" : "Deposit processed successfully",
            "data" : {
                "transaction_id": transaction.id,
                "reference": transaction.reference,
                "amount": transaction.amount,
                "balance" : transaction.balance_after,
                "status" : transaction.status,
            },
        }
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(f"Failed to proces despoit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message":"Failed to proecess deposit"},
        )
