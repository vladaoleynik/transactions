"""Persist transaction events with FX conversion and idempotent dedup.

Duplicate event ids are ignored via ON CONFLICT DO NOTHING on the primary key.
Downstream failures raise ProcessingError so the worker can retry without acking.
"""

from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, SQLModel

from app.models import Transaction, TransactionEvent
from app.rates import RateLookupError, RateService


class ProcessingError(Exception):
    """Retryable failure (FX API or database temporarily unavailable)."""


def persist_transaction(session: Session, row: Transaction) -> bool:
    """Insert row into PostgreSQL; return True if inserted, False if duplicate id."""
    table = SQLModel.metadata.tables[Transaction.__tablename__]
    query = (
        insert(table)
        .values(**row.model_dump())
        .on_conflict_do_nothing(index_elements=["id"])
        .returning(table.c.id)
    )
    inserted_id = session.exec(query).scalar_one_or_none()
    session.commit()
    return inserted_id is not None


def process_event(
    session: Session,
    event: TransactionEvent,
    rate_service: RateService,
) -> bool:
    """
    Convert event amount to USD and persist.

    Returns True when a new row was inserted, False when duplicate id was skipped.
    Raises ProcessingError when a retryable downstream dependency fails.
    """
    try:
        amount_usd = rate_service.convert_to_usd(event.amount, event.currency)
    except RateLookupError as exc:
        raise ProcessingError(str(exc)) from exc

    row = Transaction(
        id=event.id,
        user_id=event.user_id,
        amount=event.amount,
        currency=event.currency.upper(),
        timestamp=event.timestamp,
        amount_usd=amount_usd,
        processed_at=datetime.now(UTC),
    )

    try:
        return persist_transaction(session, row)
    except Exception as exc:
        session.rollback()
        raise ProcessingError("Database unavailable") from exc
