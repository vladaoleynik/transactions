from collections.abc import Generator
from unittest.mock import patch

import pytest
from app.models import Transaction  # noqa: F401
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from tests.db import persist_transaction_sqlite


@pytest.fixture(scope="session", autouse=True)
def _stub_app_startup() -> Generator[None, None, None]:
    """API tests import the FastAPI app; avoid requiring Postgres/Redis on startup."""
    with (
        patch("app.database.init_db", lambda: None),
        patch("app.main.queue.ensure_consumer_group", lambda: None),
    ):
        yield


@pytest.fixture(autouse=True)
def _use_sqlite_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route persistence through SQLite in tests; production code stays PostgreSQL-only."""
    monkeypatch.setattr("app.processing.persist_transaction", persist_transaction_sqlite)


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
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
