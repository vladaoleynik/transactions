"""Read-side queries for persisted transactions.

Used by the HTTP API to serve user summaries and paginated transaction lists.
All amounts are already converted to USD by the worker before they reach this layer.

Database failures propagate as ``SQLAlchemyError`` and are mapped to HTTP 503 by
``app.api_errors.register_exception_handlers``.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import desc
from sqlmodel import Session, col, func, select

from app.models import Transaction
from app.schemas import TransactionItem, UserSummaryResponse, UserTransactionsResponse


def get_user_summary(session: Session, user_id: str) -> UserSummaryResponse:
    """Return transaction count and total USD for a user.

    Unknown users return zero count and ``0.00`` total rather than raising.
    """
    statement = select(
        func.count(col(Transaction.id)),
        func.coalesce(func.sum(Transaction.amount_usd), 0),
    ).where(Transaction.user_id == user_id)
    transaction_count, total_usd_raw = session.exec(statement).one()
    total_usd = Decimal(total_usd_raw or 0).quantize(Decimal("0.01"))
    return UserSummaryResponse(
        user_id=user_id,
        transaction_count=transaction_count,
        total_usd=total_usd,
    )


def list_user_transactions(
    session: Session,
    user_id: str,
    *,
    from_: datetime | None = None,
    to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> UserTransactionsResponse:
    """Return a page of transactions for a user, newest first.

    ``from_`` and ``to`` filter on event ``timestamp`` (inclusive bounds).
    ``total`` reflects the filtered result set, not just the current page.
    """
    statement = select(Transaction).where(Transaction.user_id == user_id)
    if from_ is not None:
        statement = statement.where(Transaction.timestamp >= from_)
    if to is not None:
        statement = statement.where(Transaction.timestamp <= to)

    count_statement = select(func.count()).select_from(statement.subquery())
    total = session.exec(count_statement).one()

    offset = (page - 1) * page_size
    rows = session.exec(
        statement.order_by(desc(col(Transaction.timestamp))).offset(offset).limit(page_size)
    ).all()

    items = [TransactionItem.model_validate(row) for row in rows]
    return UserTransactionsResponse(
        user_id=user_id,
        page=page,
        page_size=page_size,
        total=total,
        items=items,
    )
