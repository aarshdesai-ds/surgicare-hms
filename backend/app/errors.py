"""Consistent error handling and the standard error envelope.

Every error response has the shape:

    { "error": { "code": "VALIDATION_ERROR",
                 "message": "Human readable message",
                 "fields": { "phone": "required" } } }

`fields` is optional and only present for validation errors.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging_config import get_logger

log = get_logger(__name__)


class AppError(Exception):
    """Raise this anywhere to return a structured error response."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        fields: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.fields = fields


def _envelope(code: str, message: str, fields: dict | None = None) -> dict:
    error: dict[str, Any] = {"code": code, "message": message}
    if fields:
        error["fields"] = fields
    # jsonable_encoder handles dates, Decimals, UUIDs, etc. that may appear in
    # `fields` (e.g. duplicate patient records embedded in a 409 response).
    return jsonable_encoder({"error": error})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.fields),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields: dict[str, str] = {}
        for err in exc.errors():
            # location looks like ("body", "phone"); take the last useful part
            loc = [p for p in err.get("loc", []) if p not in ("body", "query", "path")]
            key = ".".join(str(p) for p in loc) or "_"
            fields[key] = err.get("msg", "invalid")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_envelope("VALIDATION_ERROR", "Request validation failed.", fields),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "UNAUTHENTICATED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
        }.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals; log with context for debugging.
        log.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("INTERNAL_ERROR", "An unexpected error occurred."),
        )
