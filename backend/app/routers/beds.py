"""Inpatient bed board + admission endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import require_pool
from ..schemas.bed import AdmissionCreate, DischargeRequest, TransferRequest
from ..services import beds as service

router = APIRouter(prefix="/api", tags=["beds"])

_WARD = require_roles("reception", "admin", "doctor", "nurse")


@router.get("/beds")
async def list_beds(_: CurrentUser = Depends(get_current_user)) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return {"items": await service.list_beds(conn)}


@router.post("/admissions", status_code=201)
async def admit(payload: AdmissionCreate, user: CurrentUser = Depends(_WARD)) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.admit(conn, payload, user.id)


@router.post("/admissions/{admission_id}/transfer")
async def transfer(
    admission_id: int, payload: TransferRequest, user: CurrentUser = Depends(_WARD)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.transfer(conn, admission_id, payload, user.id)


@router.post("/admissions/{admission_id}/discharge")
async def discharge(
    admission_id: int, payload: DischargeRequest, user: CurrentUser = Depends(_WARD)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.discharge(conn, admission_id, payload, user.id)
