"""Liveness and readiness checks."""

from sqlalchemy import text

from app.database import engine
from app.queue import EventQueue


def check_database() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def check_redis(queue: EventQueue) -> None:
    queue.ping()
