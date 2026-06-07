"""HTTP API: accept events into the queue for async processing."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status

from app.database import init_db
from app.models import TransactionEvent
from app.queue import EventQueue

queue = EventQueue()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    queue.ensure_consumer_group()
    yield


app = FastAPI(title="Transactions", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/events", status_code=status.HTTP_202_ACCEPTED)
def ingest_event(event: TransactionEvent) -> dict[str, str]:
    # 202 = accepted for processing; persistence happens asynchronously in the worker.
    message_id = queue.publish(event)
    return {"status": "accepted", "message_id": message_id}
