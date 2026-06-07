"""Test-only SQLite persistence matching production persist_transaction semantics."""

from app.models import Transaction
from sqlalchemy.dialects.sqlite import insert
from sqlmodel import Session, SQLModel


def persist_transaction_sqlite(session: Session, row: Transaction) -> bool:
    """SQLite stand-in for app.processing.persist_transaction used in tests only."""
    table = SQLModel.metadata.tables[Transaction.__tablename__]
    stmt = (
        insert(table)
        .values(**row.model_dump())
        .on_conflict_do_nothing(index_elements=["id"])
        .returning(table.c.id)
    )
    inserted_id = session.exec(stmt).scalar_one_or_none()
    session.commit()
    return inserted_id is not None
