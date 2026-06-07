from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class TransactionEvent(SQLModel):
    """Inbound event payload from POST /events and the queue."""

    id: str
    user_id: str
    amount: Decimal
    currency: str = Field(max_length=3)
    timestamp: datetime


class Transaction(SQLModel, table=True):
    """Persisted transaction after USD conversion."""

    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_user_id_timestamp", "user_id", "timestamp"),)

    id: str = Field(primary_key=True)
    user_id: str = Field(index=True)
    amount: Decimal
    currency: str = Field(max_length=3)
    timestamp: datetime
    amount_usd: Decimal
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
