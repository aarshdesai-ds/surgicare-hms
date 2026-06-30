"""Appointment scheduling business logic.

Double-booking is prevented by the `no_doctor_overlap` exclusion constraint in
the database; here we translate that violation into a clean 409 response.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import asyncpg

from ..errors import AppError
from ..schemas.appointment import AppointmentCreate, AppointmentStatusUpdate
from ..utils.audit import write_audit

# Appointment joined with patient + doctor display fields.
_SELECT = """
    SELECT a.id, a.patient_id, a.doctor_id, a.scheduled_at, a.duration_min,
           a.status, a.reason, a.created_at,
           p.uhid AS patient_uhid,
           (p.first_name || ' ' || COALESCE(p.last_name, '')) AS patient_name,
           p.phone AS patient_phone,
           d.full_name AS doctor_name, d.specialty AS doctor_specialty
    FROM public.appointments a
    JOIN public.patients p ON p.id = a.patient_id
    JOIN public.doctors  d ON d.id = a.doctor_id
"""


async def list_doctors(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch(
        "SELECT id, full_name, specialty, consult_fee FROM public.doctors "
        "WHERE is_active = true ORDER BY full_name"
    )
    return [dict(r) for r in rows]


async def create(
    conn: asyncpg.Connection, data: AppointmentCreate, actor_id: str
) -> dict:
    # Validate references exist (clearer errors than a raw FK violation).
    if not await conn.fetchval(
        "SELECT 1 FROM public.patients WHERE id = $1", data.patient_id
    ):
        raise AppError("NOT_FOUND", "Patient not found.", status_code=404)
    if not await conn.fetchval(
        "SELECT 1 FROM public.doctors WHERE id = $1 AND is_active = true",
        data.doctor_id,
    ):
        raise AppError("NOT_FOUND", "Doctor not found.", status_code=404)

    try:
        row = await conn.fetchrow(
            """
            INSERT INTO public.appointments
                (patient_id, doctor_id, scheduled_at, duration_min, reason, created_by)
            VALUES ($1, $2, $3, $4, $5, $6::uuid)
            RETURNING id
            """,
            data.patient_id,
            data.doctor_id,
            data.scheduled_at,
            data.duration_min,
            data.reason,
            actor_id,
        )
    except asyncpg.exceptions.ExclusionViolationError as exc:
        raise AppError(
            code="SLOT_CONFLICT",
            message="This doctor already has an appointment overlapping that time.",
            status_code=409,
        ) from exc

    await write_audit(
        conn,
        actor_id=actor_id,
        action="create",
        entity="appointments",
        entity_id=row["id"],
    )
    return await get_by_id(conn, row["id"])


async def get_by_id(conn: asyncpg.Connection, appt_id: int) -> dict:
    row = await conn.fetchrow(f"{_SELECT} WHERE a.id = $1", appt_id)
    if row is None:
        raise AppError("NOT_FOUND", "Appointment not found.", status_code=404)
    return dict(row)


async def list_day(
    conn: asyncpg.Connection, day: date, doctor_id: int | None
) -> list[dict]:
    """All appointments on a given calendar day (optionally one doctor)."""
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    params: list = [start, end]
    where = "WHERE a.scheduled_at >= $1 AND a.scheduled_at < $2"
    if doctor_id is not None:
        params.append(doctor_id)
        where += " AND a.doctor_id = $3"

    rows = await conn.fetch(
        f"{_SELECT} {where} ORDER BY a.scheduled_at", *params
    )
    return [dict(r) for r in rows]


async def update_status(
    conn: asyncpg.Connection,
    appt_id: int,
    data: AppointmentStatusUpdate,
    actor_id: str,
) -> dict:
    existing = await conn.fetchval(
        "SELECT status FROM public.appointments WHERE id = $1", appt_id
    )
    if existing is None:
        raise AppError("NOT_FOUND", "Appointment not found.", status_code=404)

    try:
        await conn.execute(
            "UPDATE public.appointments SET status = $1 WHERE id = $2",
            data.status,
            appt_id,
        )
    except asyncpg.exceptions.ExclusionViolationError as exc:
        # Re-activating a cancelled/no-show slot can collide with another booking.
        raise AppError(
            code="SLOT_CONFLICT",
            message="That time slot is no longer free for this doctor.",
            status_code=409,
        ) from exc

    await write_audit(
        conn,
        actor_id=actor_id,
        action="update",
        entity="appointments",
        entity_id=appt_id,
        detail={"status": data.status},
    )
    return await get_by_id(conn, appt_id)
