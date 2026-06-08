from unittest.mock import MagicMock

import redis
from app.queue import EventQueue


def test_read_stream_returns_empty_list_when_blocking_read_times_out() -> None:
    redis_client = MagicMock()
    redis_client.xreadgroup.side_effect = redis.TimeoutError("Timeout reading from socket")
    queue = EventQueue(redis_url="redis://localhost:6379/0")
    queue._redis = redis_client

    messages = queue._read_stream(
        consumer_name="worker-1",
        stream_id=">",
        count=10,
        block_ms=5000,
    )

    assert messages == []
