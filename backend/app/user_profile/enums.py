from enum import Enum


class SalutationEnum(str, Enum):
    Mr = "Mr"
    Mrs = "Mrs"
    Miss = "Miss"


class GenderEnum(str, Enum):
    Male = "Male"
    Female = "Female"
    Other = "Other"


class MaritalStatusEnum(str, Enum):
    Married = "Married"
    Divorced = "Divorced"
    Single = "Single"
    Widowed = "Widowed"


class IdentificationTypeEnum(str, Enum):
    Passport = "Passport"
    Drivers_License = "Drivers_License"
    National_ID = "National_ID"


class EmploymentStatusEnum(str, Enum):
    Employed = "Employed"
    Unemployed = "Unemployed"
    Self_Employed = "Self_Employed"
    Student = "Student"
    Retired = "Retired"


class ImageTypeEnum(str, Enum):
    PROFILE_PHOTO = "profile_photo"
    ID_PHOTO = "id_photo"
    SIGNATURE_PHOTO = "signature_photo"