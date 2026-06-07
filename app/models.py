from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class TransactionBase(SQLModel):
    """Shared field definitions for persisted transactions (table + API read model)."""

    id: str
    user_id: str
    amount: Decimal
    currency: str = Field(max_length=3)
    timestamp: datetime
    amount_usd: Decimal
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Transaction(TransactionBase, table=True):
    """Persisted transaction after USD conversion."""

    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_user_id_timestamp", "user_id", "timestamp"),)

    id: str = Field(primary_key=True)  # dedup key; same id → effectively-once storage
    user_id: str = Field(index=True)
