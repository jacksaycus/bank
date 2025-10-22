import uuid

from fastapi import HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from backend.app.auth.models import User
from backend.app.core.logging import get_logger
from backend.app.user_profile.models import Profile
from backend.app.user_profile.schema import ProfileCreateSchema,ProfileUpdateSchema,ImageTypeSchema
from backend.app.auth.models import User
from backend.app.core.utils.image import validate_image
from backend.app.core.tasks.image_upload import upload_profile_image_task
from typing import BinaryIO

logger = get_logger()

async def get_user_profile(user_id: uuid.UUID, session: AsyncSession) -> Profile | None:
    try:
        statement = select(Profile).where(Profile.user_id == user_id)
        result = await session.exec(statement)
        return result.first()
    
    except Exception as e:
        logger.error(f"Error fetching user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status":"error", "message":"Failed to fetch user profile"},
        )
    
async def create_user_profile(
            user_id: uuid.UUID, profile_data: ProfileCreateSchema, session: AsyncSession) -> Profile:
        try:
            existing_profile = await get_user_profile(user_id, session)

            if existing_profile:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "error",
                        "message": "Profile already exists for this user",
                    },
                )
            profile_data_dict = profile_data.model_dump()

            profile = Profile(user_id=user_id, **profile_data_dict)
            session.add(profile)

            await session.commit()
            await session.refresh(profile)

            logger.info(f"Created profile for user {user_id}")
            return profile
        
        except HTTPException as http_ex:
            raise http_ex
        except Exception as e:
            logger.error(f"Error creating user profiles: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"status":"error", "message":"Failed to create user profile"},
            )
    
async def update_user_profile(
          user_id: uuid.UUID, profile_data: ProfileUpdateSchema, session: AsyncSession
) -> Profile:
     try:
          profile = await get_user_profile(user_id, session)
          if not profile:
               raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                         "status": "error",
                         "message": "Profile not found",
                         "action": "Please create a profile first",
                    },
               )
          update_data = profile_data.model_dump(exclude_unset=True)

          for field, value in update_data.items():
               if field not in [
                    "profile_phone_url",
                    "id_photo_url",
                    "signature_photo_url",
               ]:
                    setattr(profile, field, value)

          await session.commit()
          await session.refresh(profile)

          logger.info(f"Updated profile for user {user_id}")
          return profile
     
     except HTTPException as http_ex:
          raise http_ex
     except Exception as e:
          logger.error(f"Error updating user profile: {str(e)}")
          raise HTTPException(
               status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
               detail={"status": "error", "message":"Failed to update user profile"},
          )
     
def initiate_image_uplaod(
     file_content: bytes,
     image_type: ImageTypeSchema,
     content_type: str,
     user_id: uuid.UUID,
) -> str:
    try:
         task = upload_profile_image_task.delay(
              file_content, image_type.value, str(user_id), content_type
         )
         return task.id
    except Exception as e:
        logger.error(f"Error initiating image upload: {str(e)}", exc_info=True)
        raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail={"status":"error","message": "Failed to intiate image upload"},
        )

async def update_profile_image_url(
          user_id: uuid.UUID,
          image_type: ImageTypeSchema,
          image_url: str,
          session: AsyncSession,
) -> Profile:
     try:
          profile = await get_user_profile(user_id, session)
          if not profile:
               raise HTTPException(
                    status_code=status.HTTP_400_NOT_FOUND,
                    detail={
                         "status": "error",
                         "message": "Profile not found",
                         "action" : "Please crete a profile first",
                    },
               )
          field_mapping = {
               ImageTypeSchema.PROFILE_PHOTO: "profile_photo_url",
               ImageTypeSchema.ID_PHOTO: "id_photo_url",
               ImageTypeSchema.SIGNATURE_PHOTO: "signature_photo_url",
          }

          field_name = field_mapping.get(image_type)

          if not field_name:
               raise ValueError(f"Invalid image type: {image_type}")
          
          setattr(profile, field_name, image_url)

          await session.commit()

          await session.refresh(profile)

          return profile
     except HTTPException as http_ex:
          raise http_ex
     except Exception as e:
          logger.error(f"Error updating profile image url: {str(e)}")
          raise HTTPException(
               status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
               detail={"status": "error", "message": "Failed to update profile imaeg url"},
          )
     
async def get_user_with_profile(user_id: uuid.UUID, session: AsyncSession) -> User:
     try:
          statement = select(User).where(User.id == user_id)
          result = await session.exec(statement)
          user = result.first()

          if user:
               await session.refresh(user, ["profile"])
               return user
          else:
               raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"status": "error", "message": "User not found"},
               )
     except Exception as e:
          logger.error(f"Error fetching user with profile: {str(e)}")
          raise HTTPException(
               status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
               detail={"status": "error", "message": "Failed to fetch user with profile."},
          )