"""Async Postgres access via asyncpg.

The FastAPI backend connects to Supabase Postgres directly for all business
logic. It uses a service-role / direct DB connection, so **it bypasses RLS** —
RLS protects the *browser → Supabase* path, while the API enforces rules in
code (and writes the audit log). Keep privileged logic here, not in the client.
"""

from __future__ import annotations

import json

import asyncpg

from .config import settings
from .logging_config import get_logger

log = get_logger(__name__)


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Encode/decode JSONB columns as Python dicts automatically."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


class Database:
    """Holds the shared connection pool for the process lifetime."""

    pool: asyncpg.Pool | None = None


db = Database()


async def connect() -> None:
    """Open the connection pool. Resilient: a failure here logs a warning but
    does not crash the app, so the API still boots during local development
    before DATABASE_URL is configured."""
    try:
        db.pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=1,
            max_size=10,
            command_timeout=30,
            init=_init_connection,
        )
        log.info("database.connected")
    except Exception as exc:  # noqa: BLE001 - we deliberately degrade gracefully
        db.pool = None
        log.warning("database.connect_failed", error=str(exc))


async def disconnect() -> None:
    if db.pool is not None:
        await db.pool.close()
        db.pool = None
        log.info("database.disconnected")


async def ping() -> bool:
    """Return True if the database answers a trivial query."""
    if db.pool is None:
        return False
    try:
        async with db.pool.acquire() as conn:
            return (await conn.fetchval("SELECT 1")) == 1
    except Exception as exc:  # noqa: BLE001
        log.warning("database.ping_failed", error=str(exc))
        return False


def require_pool() -> asyncpg.Pool:
    """Get the pool or raise if the DB is not available (use in request paths)."""
    if db.pool is None:
        from .errors import AppError

        raise AppError(
            code="DB_UNAVAILABLE",
            message="Database is not available.",
            status_code=503,
        )
    return db.pool
