from unittest.mock import patch

from app.main import app
from fastapi.testclient import TestClient


def test_health_live() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_200_when_dependencies_are_available() -> None:
    with (
        patch("app.main.check_database"),
        patch("app.main.queue.ping"),
    ):
        response = TestClient(app).get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_returns_503_when_database_is_unavailable() -> None:
    with patch("app.main.check_database", side_effect=Exception("database down")):
        response = TestClient(app, raise_server_exceptions=False).get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not ready"}


def test_readiness_returns_503_when_redis_is_unavailable() -> None:
    with (
        patch("app.main.check_database"),
        patch("app.main.queue.ping", side_effect=Exception("redis down")),
    ):
        response = TestClient(app, raise_server_exceptions=False).get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not ready"}
