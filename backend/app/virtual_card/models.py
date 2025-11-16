import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship

from backend.app.virtual_card.schema import VirtualCardBaseSchema

if TYPE_CHECKING:
    from backend.app.auth.models import User
    from backend.app.bank_account.models import BankAccount
    
class VirtualCard(VirtualCardBaseSchema, table=True):
    id: uuid.UUID = Field(
        sa_column=Column(
            pg.UUID(as_uuid=True),
            primary_key=True,
        ),
        default_factory=uuid.uuid4,
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            onupdate=func.current_timestamp(),
        ),
    )
    cvv_hash: str | None = Field(default=None)

    available_balance: float = Field(default=0.0)
    total_topped_up: float = Field(default=0.0)
    last_top_up_date: datetime | None = Field(
        default=None,
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )
    blocked_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("CURRENT_TIMESTAMP"),
        ),
    )

    total_spend_today: float = Field(default=0.0)
    total_spend_this_month: float = Field(default=0.0)
    last_transaction_date: datetime | None = Field(default=None)
    last_transaction_amount: float  | None = Field(default=None)

    physical_card_requested_at: datetime | None = Field(default=None)
    delivery_address: str | None = Field(default=None)
    delivery_city: str | None = Field(default=None)
    delivery_country: str | None = Field(default=None)
    delivery_postal_code: str | None = Field(default=None)
    physical_card_status: str | None = Field(default=None)

    blocked_by: uuid.UUID | None = Field(foreign_key="user.id", nullable=True)

    card_metadata: dict | None = Field(default=None, sa_column=Column(JSONB))

    bank_account_id: uuid.UUID = Field(foreign_key="bankaccount.id", ondelete="CASCADE")

    bank_account: "BankAccount" = Relationship(back_populates="virtual_cards")
    blocked_by_user: "User" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "VirtualCard.blocked_by",
        }
    )

    @property
    def masked_card_number(self) -> str:
        if not self.card_number:
            return ""
        return f"**** **** **** {self.card_number[-4:]}"
    
    @property
    def last_four_digits(self) -> str:
        if not self.card_number:
            return ""
        return self.card_number[-4:]
