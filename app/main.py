"""HTTP API: accept events into the queue for async processing."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Query, status
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.api_errors import register_exception_handlers
from app.database import get_session, init_db
from app.health import check_database, check_redis
from app.queries import get_user_summary, list_user_transactions
from app.queue import queue
from app.schemas import (
    MetricsResponse,
    TransactionEvent,
    UserSummaryResponse,
    UserTransactionsResponse,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    queue.ensure_consumer_group()
    yield


app = FastAPI(title="Transactions", lifespan=lifespan)
register_exception_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness: process is running (does not check dependencies)."""
    return {"status": "ok"}


@app.get("/health/ready")
def readiness() -> JSONResponse:
    """Readiness: Postgres and Redis are reachable."""
    try:
        check_database()
        check_redis(queue)
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready"},
        )
    return JSONResponse(content={"status": "ready"})


@app.get("/metrics", response_model=MetricsResponse)
def metrics() -> MetricsResponse:
    return MetricsResponse(events_processed=queue.processed_event_count())


@app.post("/events", status_code=status.HTTP_202_ACCEPTED)
def ingest_event(event: TransactionEvent) -> dict[str, str]:
    # 202 = accepted for processing; persistence happens asynchronously in the worker.
    message_id = queue.publish(event)
    return {"status": "accepted", "message_id": message_id}


@app.get("/users/{user_id}/summary", response_model=UserSummaryResponse)
def user_summary(user_id: str, session: Session = Depends(get_session)) -> UserSummaryResponse:
    return get_user_summary(session, user_id)


@app.get("/users/{user_id}/transactions", response_model=UserTransactionsResponse)
def user_transactions(
    user_id: str,
    session: Session = Depends(get_session),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> UserTransactionsResponse:
    return list_user_transactions(
        session,
        user_id,
        from_=from_,
        to=to,
        page=page,
        page_size=page_size,
    )
