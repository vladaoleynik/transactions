import json

import redis

from app.config import settings
from app.models import TransactionEvent


class EventQueue:
    def __init__(self, redis_url: str | None = None) -> None:
        self._redis = redis.Redis.from_url(
            redis_url or settings.redis_url,
            decode_responses=True,
        )
        self._stream = settings.stream_name
        self._group = settings.consumer_group

    def ensure_consumer_group(self) -> None:
        try:
            self._redis.xgroup_create(self._stream, self._group, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def publish(self, event: TransactionEvent) -> str:
        payload = {
            "id": event.id,
            "user_id": event.user_id,
            "amount": str(event.amount),
            "currency": event.currency,
            "timestamp": event.timestamp.isoformat(),
        }
        message_id = self._redis.xadd(self._stream, {"payload": json.dumps(payload)})
        return str(message_id)
