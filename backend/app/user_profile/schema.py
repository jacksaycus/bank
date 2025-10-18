from datetime import date
from enum import Enum

from pydantic_extra_types.country import CountryShortName
from pydantic_extra_types.phone_numbers import PhoneNumber
from sqlmodel import Field, SQLModel

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
    place_of_birth: CountryShortName
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