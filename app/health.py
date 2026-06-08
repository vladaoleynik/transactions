"""Liveness and readiness checks."""

from sqlalchemy import text

import app.database as database
from app.queue import EventQueue


def check_database() -> None:
    with database.engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def check_redis(queue: EventQueue) -> None:
    queue.ping()
