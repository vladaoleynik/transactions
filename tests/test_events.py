from unittest.mock import patch

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

EVENT_PAYLOAD = {
    "id": "tx-1",
    "user_id": "user-1",
    "amount": "100.50",
    "currency": "EUR",
    "timestamp": "2026-06-07T12:00:00Z",
}


def test_ingest_event_returns_202() -> None:
    with patch("app.main.queue.publish", return_value="1717756800000-0") as publish:
        response = client.post("/events", json=EVENT_PAYLOAD)

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


def test_ingest_event_rejects_invalid_payload() -> None:
    response = client.post("/events", json={"id": "tx-1"})
    assert response.status_code == 422
