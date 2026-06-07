from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings
from app.models import Transaction  # noqa: F401  # register table with SQLModel metadata

engine = create_engine(settings.database_url, pool_pre_ping=True)


def init_db() -> None:
    # Creates missing tables only; schema changes require migrations (Alembic).
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
