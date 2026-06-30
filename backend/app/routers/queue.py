"""OPD doctors, sessions, and queue endpoints.

Reads open to active staff; writes limited to reception, admin, doctor.
"""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import require_pool
from ..schemas.queue import QueueAdd, QueueStatusUpdate, SessionUpsert
from ..services import queue as service

router = APIRouter(prefix="/api", tags=["opd"])

_WRITERS = require_roles("reception", "admin", "doctor")


@router.get("/doctors")
async def list_doctors(_: CurrentUser = Depends(get_current_user)) -> list[dict]:
    pool = require_pool()
    async with pool.acquire() as conn:
        return await service.list_doctors(conn)


# ---- sessions ----
@router.get("/opd-sessions")
async def list_sessions(
    day: date_type = Query(...),
    doctor_id: int | None = Query(None),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return {"items": await service.list_sessions(conn, day, doctor_id)}


@router.put("/opd-sessions")
async def upsert_session(
    payload: SessionUpsert, user: CurrentUser = Depends(_WRITERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.upsert_session(conn, payload, user.id)


# ---- queue ----
@router.get("/queue")
async def list_queue(
    day: date_type = Query(...),
    doctor_id: int | None = Query(None),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return {"items": await service.list_queue(conn, day, doctor_id)}


@router.post("/queue", status_code=201)
async def add_to_queue(
    payload: QueueAdd, user: CurrentUser = Depends(_WRITERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.add(conn, payload, user.id)


@router.patch("/queue/{entry_id}/status")
async def update_queue_status(
    entry_id: int,
    payload: QueueStatusUpdate,
    user: CurrentUser = Depends(_WRITERS),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.update_status(conn, entry_id, payload, user.id)
