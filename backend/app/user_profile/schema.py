from datetime import date
from enum import Enum

from pydantic_extra_types.country import CountryShortName
from pydantic_extra_types.phone_numbers import PhoneNumber
from sqlmodel import Field, SQLModel
from pydantic import field_validator
from backend.app.user_profile.utils import validate_id_dates

from backend.app.auth.schema import RoleChoicesSchema


class SalutationSchema(str, Enum):
    Mr = "Mr"
    Mrs = "Mrs"
    Miss = "Miss"

class GenderSchema(str, Enum):
    Male = "Male"
    Female = "Female"
    Other = "Other"

class MaritalSatusSchema(str, Enum):
    Married = "Married"
    Divorced = "Divorced"
    Single = "Single"
    Widowed = "Widowed"

class IdentificationTypeSchema(str, Enum):
    Passport = "Passport"
    Drivers_License = "Drivers_License"
    National_ID = "National_ID"

class EmploymentStatusSchema(str, Enum):
    Employed = "Employed"
    Unemployed = "Unemployed"
    Self_Employed = "Self_Employed"
    Student = "Student"
    Retired = "Retired"

class ProfileBaseSchema(SQLModel):
    title: SalutationSchema
    gender: GenderSchema
    date_of_birth: date
    country_of_birth: CountryShortName
    place_of_birth: str
    marital_status: MaritalSatusSchema
    means_of_identification: IdentificationTypeSchema
    id_issue_date: date
    id_expiry_date: date
    passport_number: str
    nationality: str
    phone_number: PhoneNumber
    address: str
    city: str
    country: str
    employment_status: EmploymentStatusSchema
    employer_name: str
    employer_address: str
    employer_city: str
    employer_country: CountryShortName
    annual_income: float
    date_of_employment: date
    profile_photo_url:str | None = Field(default=None)
    id_photo_url:str | None = Field(default=None)
    signature_photo_url: str | None = Field(default=None)

class ProfileCreateSchema(ProfileBaseSchema):
    @field_validator("id_expiry_date")
    def validate_id_dates(cls, v, values):
        if "id_issue_date" in values.data:
            validate_id_dates(values.data["id_issue_date"],v)
        return v
    
class ProfileUpdateSchema(ProfileBaseSchema):
    title: SalutationSchema | None = None
    gender: GenderSchema | None = None
    date_of_birth: date | None = None
    country_of_birth: CountryShortName | None = None
    place_of_birth: str | None = None
    marital_status: MaritalSatusSchema | None = None
    means_of_identification: IdentificationTypeSchema | None = None
    id_issue_date: date | None = None
    id_expiry_date: date | None = None
    passport_number: str | None = None
    nationality: str | None = None
    phone_number: PhoneNumber | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    employment_status: EmploymentStatusSchema | None = None
    employer_name: str | None = None
    employer_address: str | None = None
    employer_city: str | None = None
    employer_country: CountryShortName | None = None
    annual_income: float | None = None
    date_of_employment: date | None = None

    @field_validator("id_expiry_date")
    def validate_id_dates(cls, v:date | None, values):
        if v is not None and "id_issue_date" in values.data:
            validate_id_dates(values.data["id_issue_date"],v)
        return v
    
class ImageTypeSchema(str, Enum):
    PROFILE_PHOTO = "profile_photo"
    ID_PHOTO = "id_photo"
    SIGNATURE_PHOTO = "signature_photo"

class ProfileResponseSchema(SQLModel):
    username: str
    first_name: str
    middle_name: str
    last_name: str
    email: str
    id_no: str
    role: RoleChoicesSchema
    profile: ProfileBaseSchema | None

class Config:
    from_attributes = True

class PaginatedProfileResponseSchema(SQLModel):
    profiles: list[ProfileResponseSchema]
    total: int
    skip: int
    limit: int