"""Background consumer: read queue → convert FX → persist with dedup.

See README "Delivery semantics" for at-least-once (queue) vs effectively-once (DB).
"""

import logging
import time

from sqlmodel import Session

from app.config import settings
from app.database import engine, init_db
from app.processing import ProcessingError, process_event
from app.queue import EventQueue, queue
from app.rates import RateService
from app.schemas import TransactionEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 1.0


def handle_message(
    message_id: str,
    event: TransactionEvent,
    *,
    session: Session,
    queue: EventQueue,
    rate_service: RateService,
    retry_counts: dict[str, int],
) -> float | None:
    """
    Process one queued message.

    Returns backoff seconds when processing should be retried without acking.
    Returns None when the message was acked (success, duplicate, or dead-lettered).
    """
    try:
        inserted = process_event(session, event, rate_service)
        # Success or safe duplicate — release the message from the pending list.
        queue.ack(message_id)
        queue.record_event_processed()
        retry_counts.pop(message_id, None)
        if inserted:
            logger.info("Processed event id=%s user_id=%s", event.id, event.user_id)
        else:
            logger.info("Skipped duplicate event id=%s", event.id)
        return None
    except ProcessingError as exc:
        attempt = retry_counts.get(message_id, 0) + 1
        retry_counts[message_id] = attempt

        if attempt >= MAX_RETRIES:
            # Copy to DLQ first so the event is not lost, then ack to unblock the group.
            dead_letter_id = queue.dead_letter(message_id, event, str(exc))
            queue.ack(message_id)
            retry_counts.pop(message_id, None)
            logger.error(
                "Moved message %s to dead letter %s after %s attempts: %s",
                message_id,
                dead_letter_id,
                attempt,
                exc,
            )
            return None

        # No ack: message stays pending and read_batch("0") will redeliver it.
        delay = float(min(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)), 60.0))
        logger.warning(
            "Retryable failure for message %s (attempt %s/%s): %s; sleeping %.1fs",
            message_id,
            attempt,
            MAX_RETRIES,
            exc,
            delay,
        )
        return delay


def run_worker() -> None:
    init_db()
    queue.ensure_consumer_group()
    rate_service = RateService()
    # Tracks attempts per Redis message id (not event id) across retries.
    retry_counts: dict[str, int] = {}

    logger.info(
        "Worker started (stream=%s, group=%s, consumer=%s)",
        settings.stream_name,
        settings.consumer_group,
        settings.consumer_name,
    )

    while True:
        messages = queue.read_batch(settings.consumer_name)

        if not messages:
            continue

        for message_id, event in messages:
            with Session(engine) as session:
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


if __name__ == "__main__":
    run_worker()
