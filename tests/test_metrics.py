from unittest.mock import patch

from app.main import app
from fastapi.testclient import TestClient


def test_metrics_returns_events_processed_count() -> None:
    with patch("app.main.queue.processed_event_count", return_value=42):
        response = TestClient(app).get("/metrics")

    assert response.status_code == 200
    assert response.json() == {"events_processed": 42}


def test_metrics_reads_count_from_redis() -> None:
    with patch("app.main.queue.processed_event_count", return_value=0) as processed_count:
        TestClient(app).get("/metrics")

    processed_count.assert_called_once()
