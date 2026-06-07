"""Map infrastructure failures to consistent HTTP error responses."""

import logging

import redis
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

SERVICE_UNAVAILABLE_DETAIL = "Service temporarily unavailable"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(SQLAlchemyError)
    def database_error_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("Database error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": SERVICE_UNAVAILABLE_DETAIL},
        )

    @app.exception_handler(redis.RedisError)
    def queue_error_handler(_: Request, exc: redis.RedisError) -> JSONResponse:
        logger.exception("Queue error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": SERVICE_UNAVAILABLE_DETAIL},
        )
