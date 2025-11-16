from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.transaction import generate_user_statement
from backend.app.bank_account.enums import AccountStatusEnum
from backend.app.bank_account.models import BankAccount
from backend.app.core.celery_app import celery_app
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.transaction.schema import (
    StatementRequestSchema,
    StatementResponseSchema
)

logger = get_logger()
router = APIRouter(prefix="/bank-account")

@router.post(
    "/statement/generate",
    response_model=StatementResponseSchema,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_satement(
    request: StatementRequestSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> StatementResponseSchema:
    logger.info(f"generate_statement start......")
    try:
        if request.start_date > request.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message" : "Start date must be before end date",
                },
            )
        
        if request.account_number:
            logger.debug(f"current_user_id: {current_user.id}")
            account_query = select(BankAccount).where(
                BankAccount.account_number == request.account_number,
                BankAccount.user_id == current_user.id,
            )
            result = await session.exec(account_query)
            account = result.first()

            if not account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "status" : "error",
                        "message": "Account not found or does not belong to you",
                    },
                )
            
            if account.account_status != AccountStatusEnum.Active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message":"Cannot generate statement for inactive account",
                    },
                )
        result = await generate_user_statement(
            user_id = current_user.id,
            start_date = request.start_date,
            end_date = request.end_date,
            session=session,
            account_number=request.account_number,
        )

        celery_app.AsyncResult(result["task_id"])

        generated_at = datetime.now(timezone.utc)
        expires_at = generated_at + timedelta(hours=1)

        return StatementResponseSchema(
            status="pending",
            message="Statement generation initiated",
            task_id=result["task_id"],
            statement_id=result["statement_id"],
            generated_at=generated_at,
            expires_at=expires_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message" : "Failed to generate statement",
                "action" : "Please try again later",
            },
        )
    
@router.get("/statement/{statement_id}")
async def get_statement(statement_id: str) -> Response:
    try:
        redis_client = celery_app.backend.client
        pdf_data = redis_client.get(f"statement:{statement_id}")
        if not pdf_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "message": "Statement not found or has expired",
                },
            )
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment;filename=statement_{statement_id}.pdf"
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve statement: {e}")
    raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "error", "message": "Failed to retrieve statement"},
        )
    