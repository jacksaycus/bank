from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.api.routes.auth.deps import CurrentUser
from backend.app.api.services.next_of_kin import create_next_of_kin
from backend.app.core.db import get_session
from backend.app.core.logging import get_logger
from backend.app.next_of_kin.schema import NextOfKinCreateSchema, NextOfKinReadSchema

logger = get_logger()

router = APIRouter(prefix="/next-of-kin", tags=["next of Kin"])

@router.post(
    "/create",
    response_model=NextOfKinReadSchema,
    status_code=status.HTTP_201_CREATED,
    description = "Create a new next of kin. Maximum 3 per user, only one can be primary.",
)
async def create_next_of_kin_route(
    next_of_kin_data: NextOfKinCreateSchema,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> NextOfKinReadSchema:
    try:
        next_of_kin = await create_next_of_kin(
            user_id=current_user.id, next_of_kin_data=next_of_kin_data, session=session
        )
        logger.info(
            f"User {current_user.email} created an new next of kin: {next_of_kin.full_name}"
        )
        return next_of_kin
    except HTTPException as http_ex:
        logger.warning(
            f"Next of kin creation failed for user {current_user.email}: {http_ex.detail}"
        )
        raise http_ex
    except Exception as e:
        logger.error(f"Internal server error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status":"error","message":"Failed to create next of kin"},
        )
