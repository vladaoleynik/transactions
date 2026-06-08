"""Redis Streams queue for transaction events.

Delivery is at-least-once: messages remain in the pending list until XACK.
The worker must not ack until processing succeeds (or a duplicate is confirmed).
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import cast

import redis

from app.config import settings
from app.schemas import TransactionEvent


class EventQueue:
    def __init__(self, redis_url: str | None = None) -> None:
        self._redis = redis.Redis.from_url(
            redis_url or settings.redis_url,
            decode_responses=True,
        )
        self._stream = settings.stream_name
        self._group = settings.consumer_group
        # Separate stream for events that exceeded max retries (manual replay/inspection).
        self._dead_letter_stream = f"{self._stream}:dlq"
        self._processed_events_key = "metrics:events_processed_total"

    def ensure_consumer_group(self) -> None:
        # MKSTREAM creates the stream; workers read via XREADGROUP on this group.
        try:
            self._redis.xgroup_create(self._stream, self._group, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def publish(self, event: TransactionEvent) -> str:
        payload = self._serialize(event)
        message_id = self._redis.xadd(self._stream, {"payload": payload})
        return str(message_id)

    def read_batch(
        self,
        consumer_name: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list[tuple[str, TransactionEvent]]:
        self.ensure_consumer_group()

        # Prefer pending (unacked) messages so retries are not starved by new traffic.
        # Stream id "0" = already-delivered-but-not-acked entries in the PEL.
        pending = self._read_stream(
            consumer_name=consumer_name,
            stream_id="0",
            count=count,
            block_ms=1,
        )
        if pending:
            return pending

        # Stream id ">" = new messages never delivered to this consumer group.
        return self._read_stream(
            consumer_name=consumer_name,
            stream_id=">",
            count=count,
            block_ms=block_ms,
        )

    def ack(self, message_id: str) -> None:
        self._redis.xack(self._stream, self._group, message_id)

    def dead_letter(self, message_id: str, event: TransactionEvent, reason: str) -> str:
        # Preserve the event for ops before acking removes it from the pending list.
        dead_letter_id = self._redis.xadd(
            self._dead_letter_stream,
            {
                "payload": self._serialize(event),
                "reason": reason,
                "source_message_id": message_id,
            },
        )
        return str(dead_letter_id)

    def ping(self) -> None:
        self._redis.ping()

    def pending_message_count(self) -> int:
        try:
            summary = self._redis.xpending(self._stream, self._group)
            return int(summary["pending"])
        except redis.ResponseError:
            return 0

    def record_event_processed(self) -> None:
        self._redis.incr(self._processed_events_key)

    def processed_event_count(self) -> int:
        value = self._redis.get(self._processed_events_key)
        return int(value) if value is not None else 0

    def _read_stream(
        self,
        consumer_name: str,
        stream_id: str,
        count: int,
        block_ms: int,
    ) -> list[tuple[str, TransactionEvent]]:
        try:
            entries = self._redis.xreadgroup(
                groupname=self._group,
                consumername=consumer_name,
                streams={self._stream: stream_id},
                count=count,
                block=block_ms,
            )
        except redis.TimeoutError:
            # Blocking read expired with no messages; normal idle behaviour.
            return []
        if not entries:
            return []

        stream_entries = cast(
            list[tuple[str, list[tuple[str, dict[str, str]]]]],
            entries,
        )
        messages: list[tuple[str, TransactionEvent]] = []
        for _, stream_messages in stream_entries:
            for message_id, fields in stream_messages:
                messages.append((message_id, self._deserialize(fields["payload"])))
        return messages

    @staticmethod
    def _serialize(event: TransactionEvent) -> str:
        payload = {
            "id": event.id,
            "user_id": event.user_id,
            "amount": str(event.amount),
            "currency": event.currency,
            "timestamp": event.timestamp.isoformat(),
        }
        return json.dumps(payload)

    @staticmethod
    def _deserialize(payload_json: str) -> TransactionEvent:
        payload = json.loads(payload_json)
        return TransactionEvent(
            id=payload["id"],
            user_id=payload["user_id"],
            amount=Decimal(payload["amount"]),
            currency=payload["currency"],
            timestamp=datetime.fromisoformat(payload["timestamp"]),
        )


queue = EventQueue()
