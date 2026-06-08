"""Shared helpers for integration tests."""

import time

import app.database as database
from app.config import settings
from app.queue import EventQueue
from app.rates import RateService
from app.worker import handle_message
from sqlmodel import Session


def process_pending_events(
    queue: EventQueue,
    rate_service: RateService,
    *,
    max_rounds: int = 20,
) -> None:
    """Process all currently queued events (used in place of a background worker)."""
    retry_counts: dict[str, int] = {}
    for _ in range(max_rounds):
        messages = queue.read_batch(settings.consumer_name, block_ms=200)
        if not messages:
            return
        for message_id, event in messages:
            with Session(database.engine) as session:
                delay = handle_message(
                    message_id,
                    event,
                    session=session,
                    queue=queue,
                    rate_service=rate_service,
                    retry_counts=retry_counts,
                )
            if delay is not None:
                time.sleep(delay)
    raise AssertionError("queue still has pending messages after max_rounds")
