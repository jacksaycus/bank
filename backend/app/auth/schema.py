import uuid
from enum import Enum
from sqlmodel import SQLModel, Field
from pydantic import EmailStr,field_validator
from fastapi import HTTPException, status

class SecurityQuestionsSchema(str, Enum):
    MOTHER_MAIDEN_NAME = "mother_maiden_name"
    CHILDHOOD_FRIEND = "childhood_friend"
    FAVORITE_COLOR="favorite_color"
    BIRTH_CITY="birth_city"

@classmethod
def get_description(cls, value: "SecurityQuestionsSchema") -> str:
    descriptions = {
        cls.MOTHER_MAIDEN_NAME: "What is the name of your mother?",
        cls.CHILDHOOD_FRIEND: "What is the name of your childhood friend?",
        cls.FAVORITE_COLOR: "What is your fvorite color?",
        cls.BIRTH_CITY: "What is the name of the city your were born in?"
    }
    return descriptions.get(value, "Unknown security question")

class AccountStatusSchema(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"
    PENDING = "pending"

class RoleChoicesSchema(str, Enum):
    CUSTOMER = "customer"
    ACCOUNT_EXECUTIVE = "account_executive"
    BRANCH_MNANGER = "branch_manager"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    TELLER = "teller"

class BaseUserSchema(SQLModel):
    username: str | None = Field(default=None, max_length=12, unique=True)
    # username: Annotated[str | None , Field(default=None, max_length=12, unique=True)]
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    first_name: str = Field(max_length=30)
    last_name: str = Field(max_length=30)
    middle_name:str | None = Field(max_length=30, default=None)
    id_no: int = Field(unique=True, gt=0)
    is_active: bool = False
    is_superuser:bool = False
    security_question: SecurityQuestionsSchema = Field(max_length=30)
    account_status: AccountStatusSchema = Field(default=AccountStatusSchema.INACTIVE)
    role: RoleChoicesSchema = Field(default=RoleChoicesSchema.CUSTOMER)

class UserCreateSchema(BaseUserSchema):
    password: str = Field(min_length=8, max_length=40)
    confirm_password: str = Field(min_length=8, max_length=40)

    @field_validator("confirm_password")
    def validate_confirm_password(cls, v, values):
        if "password" in values.data and v!=values.data["password"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail = {
                    "status" : "error",
                    "message": "Password do not match",
                    "action": "Please ensure that the passwords you entered match",
                },
            )
        return v
    
class UserReadSchema(BaseUserSchema):
    id: uuid.UUID
    full_name: str              

class EmailRequestSchema(SQLModel):
    email: EmailStr

class LoginRequestSchema(SQLModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=40,
    )

class OTPVerifyRequestSchema(SQLModel):
    email: EmailStr
    otp: str = Field(
        min_length=6,
        max_length=6,
    )