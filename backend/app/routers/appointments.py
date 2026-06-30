"""Appointment + doctor endpoints.

Reads open to active staff; create/update limited to reception, admin, doctor.
"""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import require_pool
from ..schemas.appointment import AppointmentCreate, AppointmentStatusUpdate
from ..services import appointments as service

router = APIRouter(prefix="/api", tags=["appointments"])


@router.get("/doctors")
async def list_doctors(_: CurrentUser = Depends(get_current_user)) -> list[dict]:
    pool = require_pool()
    async with pool.acquire() as conn:
        return await service.list_doctors(conn)


@router.get("/appointments")
async def list_appointments(
    day: date_type = Query(..., description="Calendar day (YYYY-MM-DD)"),
    doctor_id: int | None = Query(None),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        items = await service.list_day(conn, day, doctor_id)
    return {"items": items, "day": day.isoformat()}


@router.post("/appointments", status_code=201)
async def create_appointment(
    payload: AppointmentCreate,
    user: CurrentUser = Depends(require_roles("reception", "admin", "doctor")),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.create(conn, payload, user.id)


@router.patch("/appointments/{appt_id}/status")
async def update_appointment_status(
    appt_id: int,
    payload: AppointmentStatusUpdate,
    user: CurrentUser = Depends(require_roles("reception", "admin", "doctor")),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.update_status(conn, appt_id, payload, user.id)
