from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.profile import update_user_profile
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.user_profile.models import Profile
from backend.app.user_profile.schema import ProfileUpdateSchema

logger = get_logger()

router = APIRouter(prefix="/profile")

@router.patch("/update", response_model=Profile, status_code=status.HTTP_200_OK)
async def update_profile(
    profile_data: ProfileUpdateSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> Profile:
    try:
        profile = await update_user_profile(
            user_id = current_user.id, profile_data=profile_data, session=session
        )

        logger.info(f"Profile updated for the user {current_user.id}")
        return profile

    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        logger.error(
            f"Failed to update the profile for the user {current_user.email}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status" : "error",
                "message" : "Failed to update user profile",
                "action" : "Please try again later",
            },
        )


