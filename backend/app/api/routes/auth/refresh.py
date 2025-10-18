import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.services.user_auth import user_auth_service
from backend.app.auth.utils import create_jwt_token, set_auth_cookies
from backend.app.core.config import settings
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger

logger = get_logger()

router = APIRouter(prefix="/auth")

@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_access_token(
    response: Response,
    session: AsyncSession = Depends(get_session),
    refresh_token: str | None = Cookie(None, alias=settings.COOKIE_REFRESH_NAME),
) -> dict:
    try:
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                     "status": "error",
                     "message" : "No refresh token provided",
                     "action": "Please login again",
                },
            )
        try:
            payload = jwt.decode(
                refresh_token, settings.SIGNING_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "Rrefresh token has expired",
                    "action": "Please login again",
                },
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "Invalid refresh token",
                    "action": "Please login again"
                }
            )
        if payload.get("type") != settings.COOKIE_REFRESH_NAME:
            logger.warning(
                f"Invalid token type. Expected {settings.COOKIE_REFRESH_NAME}, "
                f"got {payload.get('type')}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message" : "Invalid token type",
                    "action": "Please login again",
                },
            )
        user = await user_auth_service.get_user_by_id(payload["id"], session)
        if not user:
            logger.warning(f"User not found for ID: {payload['id']}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "status": "error",
                    "message": "User not found",
                    "action": "Please login again",
                },
            )
        await user_auth_service.validate_user_status(user)

        new_access_token = create_jwt_token(user.id)

        set_auth_cookies(response, new_access_token)

        logger.info(f"Successfully refreshed access token for user {user.email}")
        return {
            "message" : "Access token refreshed successfully",
            "user": {
                "email": user.email,
                "username": user.username,
                "first_name" : user.first_name,
                "last_name" : user.last_name,
                "full_name": user.full_name,
                "id_no" : user.id_no,
                "role" : user.role,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "satus" : "error",
                "message" : "Failed to refresh the token",
                "action": "Please try again later",
            },
        )