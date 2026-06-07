from unittest.mock import patch

import redis
from app.api_errors import SERVICE_UNAVAILABLE_DETAIL
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError


def test_returns_503_when_database_unavailable() -> None:
    with patch(
        "app.main.list_user_transactions",
        side_effect=OperationalError("SELECT 1", {}, Exception("connection refused")),
    ):
        response = TestClient(app, raise_server_exceptions=False).get("/users/user-1/transactions")

    assert response.status_code == 503
    assert response.json() == {"detail": SERVICE_UNAVAILABLE_DETAIL}


def test_returns_503_when_queue_unavailable() -> None:
    with patch("app.main.queue.publish", side_effect=redis.ConnectionError("redis down")):
        response = TestClient(app, raise_server_exceptions=False).post(
            "/events",
            json={
                "id": "tx-1",
                "user_id": "user-1",
                "amount": "10.00",
                "currency": "EUR",
                "timestamp": "2026-06-07T12:00:00Z",
            },
        )

    assert response.status_code == 503
    assert response.json() == {"detail": SERVICE_UNAVAILABLE_DETAIL}
