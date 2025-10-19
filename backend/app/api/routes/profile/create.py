from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.profile import create_user_profile
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.user_profile.models import Profile
from backend.app.user_profile.schema import ProfileCreateSchema

logger = get_logger()

router = APIRouter(prefix="/profile")

@router.post(
    "/create", response_model=ProfileCreateSchema, status_code=status.HTTP_201_CREATED
)
async def create_profile(
    profile_data: ProfileCreateSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> Profile:
    try:
        profile = await create_user_profile(
            user_id=current_user.id, profile_data=profile_data, session=session
        )

        logger.info(f"Created profile for {current_user.email}")
        return profile
    
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(
            f"Failed to create a profile for the use {current_user.email}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "Failed to create user profile",
                "action" : "Please try again later",
            },
        )