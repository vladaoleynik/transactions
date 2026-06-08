from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from app.processing import ProcessingError
from app.queue import EventQueue
from app.rates import RateService
from app.schemas import TransactionEvent
from app.worker import MAX_RETRIES, handle_message
from sqlmodel import Session


@pytest.fixture
def event() -> TransactionEvent:
    return TransactionEvent(
        id="tx-1",
        user_id="user-1",
        amount=Decimal("10.00"),
        currency="EUR",
        timestamp=datetime(2026, 6, 7, tzinfo=UTC),
    )


def test_handle_message_acks_on_success(
    event: TransactionEvent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = MagicMock(spec=EventQueue)
    rate_service = MagicMock(spec=RateService)
    session = MagicMock(spec=Session)
    monkeypatch.setattr("app.worker.process_event", lambda *_args, **_kwargs: True)

    delay = handle_message(
        "1-0",
        event,
        session=session,
        queue=queue,
        rate_service=rate_service,
        retry_counts={},
    )

    assert delay is None
    queue.ack.assert_called_once_with("1-0")
    queue.record_event_processed.assert_called_once()
    queue.dead_letter.assert_not_called()


def test_handle_message_does_not_ack_on_transient_failure(
    event: TransactionEvent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = MagicMock(spec=EventQueue)
    rate_service = MagicMock(spec=RateService)
    session = MagicMock(spec=Session)

    def fail(*_args: object, **_kwargs: object) -> bool:
        raise ProcessingError("Database unavailable")

    monkeypatch.setattr("app.worker.process_event", fail)

    delay = handle_message(
        "1-0",
        event,
        session=session,
        queue=queue,
        rate_service=rate_service,
        retry_counts={},
    )

    assert delay == 1.0
    queue.ack.assert_not_called()
    queue.dead_letter.assert_not_called()


def test_handle_message_moves_to_dead_letter_after_max_retries(
    event: TransactionEvent,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue = MagicMock(spec=EventQueue)
    queue.dead_letter.return_value = "dlq-1"
    rate_service = MagicMock(spec=RateService)
    session = MagicMock(spec=Session)

    def fail(*_args: object, **_kwargs: object) -> bool:
        raise ProcessingError("Database unavailable")

    monkeypatch.setattr("app.worker.process_event", fail)

    delay = handle_message(
        "1-0",
        event,
        session=session,
        queue=queue,
        rate_service=rate_service,
        retry_counts={"1-0": MAX_RETRIES - 1},
    )

    assert delay is None
    queue.dead_letter.assert_called_once()
    queue.ack.assert_called_once_with("1-0")
