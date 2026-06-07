"""Test data factories (factory_boy)."""

from datetime import UTC, datetime
from decimal import Decimal

import factory
from app.models import Transaction
from factory.alchemy import SQLAlchemyModelFactory


class TransactionFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Transaction
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: f"tx-{n}")
    user_id = factory.Sequence(lambda n: f"user-{n}")
    amount = Decimal("10.00")
    currency = "EUR"
    timestamp = factory.LazyFunction(lambda: datetime(2026, 6, 1, tzinfo=UTC))
    amount_usd = Decimal("12.00")
    processed_at = factory.LazyFunction(lambda: datetime(2026, 6, 7, tzinfo=UTC))
