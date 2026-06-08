from datetime import datetime
from decimal import Decimal

from sqlmodel import Field, SQLModel

from app.models import TransactionBase


class TransactionEvent(SQLModel):
    """Inbound event payload from POST /events and the queue."""

    id: str
    user_id: str
    amount: Decimal
    currency: str = Field(max_length=3)
    timestamp: datetime


class UserSummaryResponse(SQLModel):
    user_id: str
    transaction_count: int
    total_usd: Decimal


class TransactionItem(TransactionBase):
    """API read model; inherits field definitions from the transactions table base."""


class UserTransactionsResponse(SQLModel):
    user_id: str
    page: int
    page_size: int
    total: int
    items: list[TransactionItem]


class MetricsResponse(SQLModel):
    events_processed: int


class IngestEventResponse(SQLModel):
    status: str
    message_id: str
