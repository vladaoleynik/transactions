from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.factories import TransactionEventFactory, TransactionFactory


def test_ingest_event_returns_202(client: TestClient) -> None:
    payload = TransactionEventFactory.build(
        id="tx-1",
        user_id="user-1",
        amount=Decimal("100.50"),
    ).model_dump(mode="json")

    with patch("app.main.queue.publish", return_value="1717756800000-0") as publish:
        response = client.post("/events", json=payload)

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "message_id": "1717756800000-0",
    }
    publish.assert_called_once()
    event = publish.call_args.args[0]
    assert event.id == "tx-1"
    assert event.user_id == "user-1"
    assert str(event.amount) == "100.50"
    assert event.currency == "EUR"


def test_ingest_event_rejects_invalid_payload(client: TestClient) -> None:
    response = client.post("/events", json={"id": "tx-1"})

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert isinstance(errors, list)
    assert len(errors) >= 1

    missing_fields = {error["loc"][-1] for error in errors if error["type"] == "missing"}
    assert "user_id" in missing_fields
    assert "amount" in missing_fields
    assert "currency" in missing_fields
    assert "timestamp" in missing_fields


def test_user_summary_returns_total_and_count(
    client: TestClient,
    transaction_factory: type[TransactionFactory],
) -> None:
    transaction_factory.create(
        id="tx-1",
        user_id="user-1",
        amount="10.00",
        amount_usd="12.00",
        timestamp=datetime(2026, 6, 1, tzinfo=UTC),
    )
    transaction_factory.create(
        id="tx-2",
        user_id="user-1",
        amount="20.00",
        amount_usd="25.00",
        timestamp=datetime(2026, 6, 2, tzinfo=UTC),
    )

    response = client.get("/users/user-1/summary")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-1",
        "transaction_count": 2,
        "total_usd": "37.00",
    }


def test_user_summary_for_unknown_user_returns_zeros(client: TestClient) -> None:
    response = client.get("/users/unknown/summary")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "unknown",
        "transaction_count": 0,
        "total_usd": "0.00",
    }


def test_user_transactions_supports_date_filter_and_pagination(
    client: TestClient,
    transaction_factory: type[TransactionFactory],
) -> None:
    transaction_factory.create(
        id="tx-1",
        user_id="user-1",
        amount="10.00",
        amount_usd="12.00",
        timestamp=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
    )
    transaction_factory.create(
        id="tx-2",
        user_id="user-1",
        amount="20.00",
        amount_usd="25.00",
        timestamp=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
    )
    transaction_factory.create(
        id="tx-3",
        user_id="user-1",
        amount="30.00",
        amount_usd="35.00",
        timestamp=datetime(2026, 6, 5, 12, 0, tzinfo=UTC),
    )

    response = client.get(
        "/users/user-1/transactions",
        params={
            "from": "2026-06-02T00:00:00Z",
            "to": "2026-06-04T23:59:59Z",
            "page": 1,
            "page_size": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "user-1"
    assert payload["total"] == 1
    assert payload["page"] == 1
    assert payload["page_size"] == 10
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == "tx-2"


def test_metrics_returns_events_processed_count(client: TestClient) -> None:
    with patch("app.main.queue.processed_event_count", return_value=42):
        response = client.get("/metrics")

    assert response.status_code == 200
    assert response.json() == {"events_processed": 42}
