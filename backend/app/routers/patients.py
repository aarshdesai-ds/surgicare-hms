"""Patient management endpoints.

Reads are open to any active staff; create/update are limited to reception and
admin via require_roles. Business logic lives in services/patients.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import require_pool
from ..schemas.patient import PatientCreate, PatientUpdate
from ..services import patients as service

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("")
async def list_patients(
    q: str = Query("", description="Search by UHID, phone, or name"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        items, total = await service.search(conn, q, limit, offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("", status_code=201)
async def create_patient(
    payload: PatientCreate,
    force: bool = Query(False, description="Register even if a duplicate exists"),
    user: CurrentUser = Depends(require_roles("reception", "admin")),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.create(conn, payload, user.id, force=force)


@router.get("/{patient_id}")
async def get_patient(
    patient_id: int,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.get_by_id(conn, patient_id, user.id)


@router.put("/{patient_id}")
async def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    user: CurrentUser = Depends(require_roles("reception", "admin")),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.update(conn, patient_id, payload, user.id)
