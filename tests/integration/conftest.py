"""Fixtures for Postgres + Redis integration tests (testcontainers)."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import app.database as database
import app.main as main_module
import app.queue as queue_module
import pytest
from app.database import init_db
from app.main import app
from app.models import Transaction  # noqa: F401
from app.queue import EventQueue
from app.rates import RateService
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import SQLModel, create_engine
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from tests.integration.helpers import process_pending_events


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    try:
        with PostgresContainer("postgres:16-alpine") as postgres:
            yield postgres
    except Exception as exc:
        pytest.skip(f"Docker is required for integration tests: {exc}")


@pytest.fixture(scope="session")
def redis_container() -> Generator[RedisContainer, None, None]:
    try:
        with RedisContainer("redis:7-alpine") as redis:
            yield redis
    except Exception as exc:
        pytest.skip(f"Docker is required for integration tests: {exc}")


@pytest.fixture(scope="session")
def integration_stack(
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
) -> Generator[dict[str, Any], None, None]:
    postgres_url = postgres_container.get_connection_url()
    redis_host = redis_container.get_container_host_ip()
    redis_port = redis_container.get_exposed_port(6379)
    redis_url = f"redis://{redis_host}:{redis_port}/0"

    engine = create_engine(postgres_url, pool_pre_ping=True)
    SQLModel.metadata.create_all(engine)
    database.engine = engine

    queue = EventQueue(redis_url=redis_url)
    queue_module.queue = queue
    main_module.queue = queue
    queue.ensure_consumer_group()

    yield {"engine": engine, "queue": queue}

    engine.dispose()


@pytest.fixture(autouse=True)
def reset_integration_state(integration_stack: dict[str, Any]) -> Generator[None, None, None]:
    engine = integration_stack["engine"]
    queue: EventQueue = integration_stack["queue"]

    with engine.connect() as connection:
        connection.execute(text("DELETE FROM transactions"))
        connection.commit()
    queue._redis.flushdb()
    queue.ensure_consumer_group()
    yield


@pytest.fixture
def integration_client(integration_stack: dict[str, Any]) -> Generator[TestClient, None, None]:
    init_db()
    integration_stack["queue"].ensure_consumer_group()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def rate_service() -> RateService:
    mock_client = MagicMock()
    mock_response = mock_client.get.return_value
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"rates": {"USD": "1.25"}}
    return RateService(client=mock_client, cache_ttl_seconds=3600)


@pytest.fixture
def process_queue(integration_stack: dict[str, Any], rate_service: RateService):
    queue: EventQueue = integration_stack["queue"]

    def _process() -> None:
        process_pending_events(queue, rate_service)

    return _process
