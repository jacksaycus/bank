from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.services.user_auth import user_auth_service
from backend.app.auth.schema import (
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
)
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.core.services.password_reset import send_password_reset_email

logger = get_logger()

router = APIRouter(prefix="/auth")

@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
async def request_password_reset(
    reset_data: PasswordResetRequestSchema, session: AsyncSession = Depends(get_session)
) -> dict:
    try:
        user = await user_auth_service.get_user_by_email(
            reset_data.email, session, include_inactive=True
        )

        if user:
            await send_password_reset_email(user.email, user.id)

        return {
            "message": "If an account exists with this email,"
            "you will receive password reset insutructions shortly "
        }
    except Exception as e:
        logger.error(f"Password reset request failed: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to processs password reset request.",
                "action": "Please try again later",
            },
        )
    

@router.post("/reset-password/{token}", status_code=status.HTTP_200_OK)
async def reset_password(
        token: str,
        reset_data: PasswordResetConfirmSchema,
        session: AsyncSession = Depends(get_session),
    ):
        try:
            await user_auth_service.reset_password(
                token,
                reset_data.new_password,
                session,
            )
            return {"message": "Password has been reset successfull"}
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message" : str(e),
                    "action": "Please request a new password reset link",
                },
            )
        except Exception as e:
             
             logger.error(f"Password reset failed: {e}")
             raise HTTPException(
                  status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                  detail={
                       "status": "error",
                       "message": "Failed to reset password.",
                       "action": "Please try again later."
                  },
             )
        