"""FastAPI application factory and entrypoint.

Run locally:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import settings
from .database import connect, disconnect
from .errors import register_error_handlers
from .logging_config import configure_logging, get_logger
from .routers import (
    beds, billing, dashboard, encounters, health, ot, patients, prescriptions,
    queue, reports, staff,
)

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    log.info("app.startup", environment=settings.environment, version=__version__)
    await connect()
    yield
    await disconnect()
    log.info("app.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="HMS API",
        version=__version__,
        description="Hospital Management System backend (FastAPI + Supabase).",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(patients.router)
    app.include_router(queue.router)
    app.include_router(dashboard.router)
    app.include_router(ot.router)
    app.include_router(encounters.router)
    app.include_router(reports.router)
    app.include_router(staff.router)
    app.include_router(billing.router)
    app.include_router(beds.router)
    app.include_router(prescriptions.router)
    return app


app = create_app()
