import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql as pg
from sqlmodel import Column, Field, Relationship

from backend.app.next_of_kin.schema import NextOfKinBaseSchema

if TYPE_CHECKING:
    from backend.app.auth.models import User

class NextOfKin(NextOfKinBaseSchema, table=True):
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
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")

    user: "User" = Relationship(back_populates="next_of_kins")