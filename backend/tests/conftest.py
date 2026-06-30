"""Shared pytest fixtures.

Two tiers of tests:
  * Unit tests — run anywhere, no database (validation, RBAC, error envelopes).
  * Integration tests — exercise real service logic against Postgres. They are
    skipped unless TEST_DATABASE_URL is set. Each runs inside a transaction that
    is ROLLED BACK afterwards, so nothing is persisted — safe to point at your
    Supabase DB (use a throwaway / test project if you prefer). Note: UHID and
    identity sequences are non-transactional, so their counters advance even on
    rollback (harmless).
"""

from __future__ import annotations

import json
import os

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.main import create_app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

# A fixed far-future date so token/position sequences start clean regardless of
# any real data in the target database.
import datetime as _dt
TEST_DATE = _dt.date(2099, 1, 1)


@pytest.fixture()
def client() -> TestClient:
    # Boots without a DB (connect() degrades gracefully) — fine for unit/API
    # error tests that never reach the database layer.
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest_asyncio.fixture()
async def conn():
    """A transaction-scoped asyncpg connection; rolled back after each test."""
    if not TEST_DATABASE_URL:
        pytest.skip("set TEST_DATABASE_URL to run integration tests")

    import asyncpg

    c = await asyncpg.connect(TEST_DATABASE_URL)
    await c.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )
    tr = c.transaction()
    await tr.start()
    try:
        yield c
    finally:
        await tr.rollback()
        await c.close()
