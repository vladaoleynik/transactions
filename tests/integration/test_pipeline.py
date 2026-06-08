from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from tests.factories import TransactionEventFactory


@pytest.mark.integration
def test_event_flows_through_queue_to_read_apis(
    integration_client: TestClient,
    process_queue,
) -> None:
    payload = TransactionEventFactory.build(
        id="integration-tx-1",
        user_id="user-integration",
        amount=Decimal("100.00"),
        currency="EUR",
    ).model_dump(mode="json")

    ingest = integration_client.post("/events", json=payload)
    assert ingest.status_code == 202

    process_queue()

    summary = integration_client.get("/users/user-integration/summary")
    assert summary.status_code == 200
    assert summary.json() == {
        "user_id": "user-integration",
        "transaction_count": 1,
        "total_usd": "125.00",
    }

    metrics = integration_client.get("/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["events_processed"] == 1


@pytest.mark.integration
def test_duplicate_event_ids_are_deduped(
    integration_client: TestClient,
    process_queue,
) -> None:
    payload = TransactionEventFactory.build(
        id="integration-tx-dup",
        user_id="user-dup",
        amount=Decimal("10.00"),
        currency="USD",
    ).model_dump(mode="json")

    assert integration_client.post("/events", json=payload).status_code == 202
    assert integration_client.post("/events", json=payload).status_code == 202

    process_queue()

    summary = integration_client.get("/users/user-dup/summary")
    assert summary.json()["transaction_count"] == 1
    assert summary.json()["total_usd"] == "10.00"
    assert integration_client.get("/metrics").json()["events_processed"] == 2


@pytest.mark.integration
def test_readiness_succeeds_with_real_dependencies(integration_client: TestClient) -> None:
    response = integration_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
