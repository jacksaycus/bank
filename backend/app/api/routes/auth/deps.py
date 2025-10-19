import jwt
from typing import Annotated
from fastapi import Depends,Cookie, HTTPException,status
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.app.core.config import settings
from backend.app.auth.models import User
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger

logger = get_logger()

async def get_current_user(
        session: AsyncSession = Depends(get_session),
        access_token: str | None = Cookie(None, alias=settings.COOKIE_ACCESS_NAME),
) -> User:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "message": "Not Authenticated",
                "action" : "Please login to access this resource",
            }
        )
    
    try:
        payload = jwt.decode(
            access_token,
            settings.SIGNING_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != settings.COOKIE_ACCESS_NAME:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail = {
                    "status" : "error",
                    "message" : "Invalid token type",
                    "action": "Please login to access this resource",
                },
            )
        
        from backend.app.api.services.user_auth import user_auth_service

        user = await user_auth_service.get_user_by_id(payload["id"], session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail = {
                    "status": "error",
                    "message" : "User not found",
                    "action": "Please login again"
                },
            )
        await user_auth_service.validate_user_status(user)
        return user
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status" : "error",
                "message" : "Token has expired",
                "action" : "Please log in action",
            },
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "message" : "Invalid token",
                "action" : "Please log in again"
            },
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message" : "Authentication failed",
                "action" : "Please try again later",
            },
        )
    
CurrentUser = Annotated[User, Depends(get_current_user)]
