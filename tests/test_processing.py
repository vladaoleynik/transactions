from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import httpx
import pytest
from app.models import Transaction
from app.processing import ProcessingError, process_event
from app.rates import RateService
from app.schemas import TransactionEvent
from sqlmodel import Session, select


class FixedRateService(RateService):
    def __init__(self, rate: Decimal) -> None:
        super().__init__(client=MagicMock())
        self._rate = rate

    def convert_to_usd(self, amount: Decimal, currency: str) -> Decimal:
        if currency.upper() == "USD":
            return amount
        return (amount * self._rate).quantize(Decimal("0.000001"))


def test_deduplicates_by_event_id(session: Session) -> None:
    rate_service = FixedRateService(rate=Decimal("1.25"))
    event = TransactionEvent(
        id="tx-1",
        user_id="user-1",
        amount=Decimal("8.00"),
        currency="EUR",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert process_event(session, event, rate_service) is True
    assert process_event(session, event, rate_service) is False

    rows = session.exec(select(Transaction)).all()
    assert len(rows) == 1
    assert rows[0].id == "tx-1"


def test_currency_conversion_to_usd(session: Session) -> None:
    mock_client = MagicMock()
    mock_response = mock_client.get.return_value
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"rates": {"USD": "1.25"}}

    rate_service = RateService(client=mock_client)
    event = TransactionEvent(
        id="tx-2",
        user_id="user-2",
        amount=Decimal("100.00"),
        currency="EUR",
        timestamp=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert process_event(session, event, rate_service) is True

    stored = session.exec(select(Transaction).where(Transaction.id == "tx-2")).one()
    assert stored.amount_usd == Decimal("125.000000")


def test_raises_processing_error_when_rate_lookup_fails(session: Session) -> None:
    mock_client = MagicMock()
    mock_client.get.side_effect = httpx.HTTPError("service unavailable")
    rate_service = RateService(client=mock_client)
    event = TransactionEvent(
        id="tx-3",
        user_id="user-3",
        amount=Decimal("10.00"),
        currency="EUR",
        timestamp=datetime(2026, 1, 3, tzinfo=UTC),
    )

    with pytest.raises(ProcessingError, match="Failed to fetch rate"):
        process_event(session, event, rate_service)

    assert session.exec(select(Transaction)).all() == []
