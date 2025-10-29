from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.next_of_kin.models import NextOfKin
from backend.app.next_of_kin.schema import (
    NextOfKinCreateSchema,
    NextOfKinReadSchema,
    NextOfKinUpdateSchema,
)

logger = get_logger()

async def get_next_of_kin_count(user_id: UUID, session: AsyncSession) -> int:
    statment = select(NextOfKin).where(NextOfKin.user_id == user_id)
    result = await session.exec(statment)
    return len(result.all())

async def get_primary_next_of_kin(
        user_id: UUID, session: AsyncSession
) -> NextOfKin | None:
    statement = select(NextOfKin).where(
        NextOfKin.user_id == user_id, NextOfKin.is_primary
    )
    result = await session.exec(statement)
    return result.first()

async def validate_next_of_kin_creation(
        user_id: UUID, is_priamry: bool, session: AsyncSession
) -> None:
    current_count = await get_next_of_kin_count(user_id, session)
    if current_count >=3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": "Maximum number of kin (3) alreay reached.",
            },
        )
    
    if is_priamry:
        existing_primary = await get_primary_next_of_kin(user_id, session)
        if existing_primary:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "status": "error",
                    "message": "A primary next of kin already exists.",
                },
            )
        
async def create_next_of_kin(
        user_id: UUID, next_of_kin_data: NextOfKinCreateSchema, session: AsyncSession
) -> NextOfKinReadSchema:
    try:
        current_count = await validate_next_of_kin_creation(
            user_id, next_of_kin_data.is_primary, session
        )

        if current_count == 0:
            next_of_kin_data.is_primary = True

        next_of_kin = NextOfKin(**next_of_kin_data.model_dump())
        next_of_kin.user_id = user_id

        session.add(next_of_kin)
        await session.commit()
        await session.refresh(next_of_kin)

        logger.info(f"Next of kin created successfully for user: {user_id}")

        return NextOfKinReadSchema.model_validate(next_of_kin)
    
    except HTTPException as http_ex:
        raise http_ex
    
    except Exception as e:
        logger.error(f"Failed to create next of kin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status":"error", "message": "Failed to create next of kin"},
        )
    