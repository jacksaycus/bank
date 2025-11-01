from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel

from backend.app.bank_account.enums import (
    AccountCurrencyEnum,
    AccountStatusEnum,
    AccountTypeEnum,
)

class BankAccountBaseSchema(SQLModel):
    account_type: AccountTypeEnum
    currency: AccountCurrencyEnum
    account_status: AccountStatusEnum = Field(default=AccountStatusEnum.Pending)
    account_number: str | None = Field(default=None, unique=True, index=True)
    account_name: str
    balance: float = Field(default=0.0)
    is_primary: bool = Field(default=False)
    kyc_submitted: bool = Field(default=False)
    kyc_verified: bool = Field(default=False)
    kyc_verified_by: UUID | None = Field(default=None)
    interest_rate: float = Field(default=0.0)

class BankAccountCreateSchema(BankAccountBaseSchema):
    account_number: str | None = None


class BankAccountReadSchema(BankAccountBaseSchema):
    id: UUID
    user_id: UUID
    account_number: str | None = None
    crated_at: datetime
    updated_at: datetime

class BankAccountUpdateSchema(BankAccountBaseSchema):
    account_name: str | None = None
    is_primary: bool | None = None
    account_status: AccountStatusEnum | None = None
 
