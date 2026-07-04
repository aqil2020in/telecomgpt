"""TNIC exception types and FastAPI handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tnic.logging_config import get_logger

log = get_logger(__name__)


class TNICError(Exception):
    """Base TNIC application error."""

    status_code: int = 500

    def __init__(self, message: str, *, detail: dict | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class ValidationError(TNICError):
    status_code = 422


class NotFoundError(TNICError):
    status_code = 404


class IngestionError(TNICError):
    status_code = 400


class RCAError(TNICError):
    status_code = 500


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TNICError)
    async def tnic_error_handler(_request: Request, exc: TNICError) -> JSONResponse:
        log.warning("TNICError: %s", exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "error": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "Internal server error", "detail": {"type": type(exc).__name__}},
        )
