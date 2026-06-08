from collections.abc import Generator
from unittest.mock import patch

import pytest
from app.database import get_session
from app.main import app
from app.models import Transaction  # noqa: F401
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from tests.db import persist_transaction_sqlite
from tests.factories import TransactionFactory


@pytest.fixture(scope="session", autouse=True)
def _stub_app_startup() -> Generator[None, None, None]:
    """API tests import the FastAPI app; avoid requiring Postgres/Redis on startup."""
    with (
        patch("app.database.init_db", lambda: None),
        patch("app.main.init_db", lambda: None),
        patch("app.queue.queue.ensure_consumer_group", lambda: None),
    ):
        yield


@pytest.fixture(autouse=True)
def _use_sqlite_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route persistence through SQLite in tests; production code stays PostgreSQL-only."""
    monkeypatch.setattr("app.processing.persist_transaction", persist_transaction_sqlite)


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    # StaticPool keeps one in-memory SQLite connection across TestClient worker threads.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture(autouse=True)
def clean_transactions(engine: Engine) -> Generator[None, None, None]:
    with engine.connect() as connection:
        connection.execute(text("DELETE FROM transactions"))
        connection.commit()
    yield


@pytest.fixture
def session(engine: Engine) -> Generator[Session, None, None]:
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    def override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def transaction_factory(session: Session) -> type[TransactionFactory]:
    TransactionFactory._meta.sqlalchemy_session = session  # type: ignore[attr-defined]
    return TransactionFactory
