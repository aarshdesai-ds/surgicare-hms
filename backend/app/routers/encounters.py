"""Clinical encounter endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import require_pool
from ..schemas.encounter import EncounterCreate
from ..services import encounters as service

router = APIRouter(prefix="/api", tags=["encounters"])

_WRITERS = require_roles("reception", "admin", "doctor")


@router.get("/encounters")
async def list_encounters(
    patient_id: int = Query(...),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return {"items": await service.list_for_patient(conn, patient_id)}


@router.post("/encounters", status_code=201)
async def create_encounter(
    payload: EncounterCreate, user: CurrentUser = Depends(_WRITERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.create(conn, payload, user.id)
