"""Operation theatre + case endpoints.

Reads open to active staff; writes limited to reception, admin, doctor.
"""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import require_pool
from ..schemas.ot import OTCaseCreate, OTMove, OTStatusUpdate
from ..services import ot as service

router = APIRouter(prefix="/api", tags=["ot"])

_WRITERS = require_roles("reception", "admin", "doctor")


@router.get("/theatres")
async def list_theatres(_: CurrentUser = Depends(get_current_user)) -> list[dict]:
    pool = require_pool()
    async with pool.acquire() as conn:
        return await service.list_theatres(conn)


@router.get("/ot-cases")
async def list_cases(
    day: date_type = Query(...),
    theatre_id: int | None = Query(None),
    surgeon_id: int | None = Query(None),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return {"items": await service.list_cases(conn, day, theatre_id, surgeon_id)}


@router.post("/ot-cases", status_code=201)
async def add_case(payload: OTCaseCreate, user: CurrentUser = Depends(_WRITERS)) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.add(conn, payload, user.id)


@router.patch("/ot-cases/{case_id}/status")
async def update_case_status(
    case_id: int, payload: OTStatusUpdate, user: CurrentUser = Depends(_WRITERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.update_status(conn, case_id, payload, user.id)


@router.patch("/ot-cases/{case_id}/move")
async def move_case(
    case_id: int, payload: OTMove, user: CurrentUser = Depends(_WRITERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.move(conn, case_id, payload, user.id)
