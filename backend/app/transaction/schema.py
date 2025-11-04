import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import Query
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel
from typing_extensions import Annotated

from backend.app.transaction.enums import (
    TransactionCategoryEnum,
    TransactionStatusEnum,
    TransactionTypeEnum,
)

class TransactionBaseSchema(SQLModel):
    amount: Annotated[Decimal, Field(decimal_places=2, ge=0)]
    description: str = Field(max_length=250)
    reference: str = Field(unique=True, index=True)
    transaction_type: TransactionTypeEnum
    transaction_category: TransactionCategoryEnum
    status: TransactionStatusEnum = Field(default=TransactionStatusEnum.Pending)
    balance_before: Annotated[Decimal, Field(decimal_places=2)]
    balance_after: Annotated[Decimal, Field(decimal_places=2)]

    transaction_metadata: dict | None = Field(default=None, sa_column=Column(JSONB))

    failed_reason: str | None = Field(default=None)
    
class TransactionCreateSchema(TransactionBaseSchema):
    pass

class TransactionReadSchema(TransactionBaseSchema):
    id: uuid.UUID
    
    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False)
    )

    completed_at: datetime | None = Field(
        default=None, sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=True)
    )

class TransactionUpdateSchema(TransactionBaseSchema):
    pass

class DepositRequestSchema(SQLModel):
    account_id: uuid.UUID
    amount:Decimal = Field(ge=0, decimal_places=2)

    description: str = Field(max_length=250)

class TransferRequestSchema(SQLModel):
    sender_account_id: uuid.UUID
    receiver_account_number: str = Field(min_length=16, max_length=16)
    amount: Decimal = Field(ge=0, decimal_places=2)
    security_answer: str = Field(max_length=30)
    description: str = Field(max_length=250)

class TransferOTPVerificationsSchema(SQLModel):
    transfer_reference: str
    otp: str = Field(min_length=6, max_length=6)

class TransferResponseSchema(SQLModel):
    status: str
    message: str
    data: dict | None = None

class CurrencyConversionSchema(SQLModel):
    amount: Decimal
    from_currency: str
    to_currency: str
    exchange_rate: Decimal
    original_amount: Decimal
    converted_amount: Decimal
    conversion_fee: Decimal = Field(default=Decimal("0.00"))
    