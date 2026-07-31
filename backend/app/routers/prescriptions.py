"""Prescription + pharmacy outbox endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import require_pool
from ..schemas.prescription import PrescriptionCreate
from ..services import pharmacy as service

router = APIRouter(prefix="/api", tags=["pharmacy"])

_WRITERS = require_roles("reception", "admin", "doctor", "nurse")


@router.post("/prescriptions", status_code=201)
async def create_prescription(
    payload: PrescriptionCreate, user: CurrentUser = Depends(_WRITERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.create(conn, payload, user.id)


@router.get("/prescriptions")
async def list_prescriptions(
    patient_id: int = Query(...),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return {"items": await service.list_for_patient(conn, patient_id)}


@router.get("/prescriptions/{rx_id}")
async def get_prescription(
    rx_id: int, _: CurrentUser = Depends(get_current_user)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return await service.get_by_id(conn, rx_id)


@router.get("/pharmacy/outbox")
async def list_outbox(
    status: str = Query("pending"),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return {"items": await service.list_outbox(conn, status)}


@router.post("/pharmacy/outbox/{outbox_id}/sent")
async def mark_sent(
    outbox_id: int, user: CurrentUser = Depends(_WRITERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.mark_sent(conn, outbox_id, user.id)
