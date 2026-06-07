from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from app.database import get_session
from app.main import app
from fastapi.testclient import TestClient
from sqlmodel import Session

from tests.factories import TransactionFactory


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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
