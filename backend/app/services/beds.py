"""Inpatient bed board + admission lifecycle (admit / transfer / discharge).

Bed occupancy is kept consistent by updating the bed status inside the same
transaction as the admission, with a row lock on the bed to prevent two
patients grabbing the same bed.
"""

from __future__ import annotations

import asyncpg

from ..errors import AppError
from ..schemas.bed import AdmissionCreate, DischargeRequest, TransferRequest
from ..utils.audit import write_audit

_BED_BASE = """
    SELECT b.id, b.room_no, b.bed_label, b.ward_type, b.daily_charge, b.status,
           a.id AS admission_id, a.admitted_at, a.diagnosis, a.attending_doctor_id,
           a.patient_id,
           (p.first_name || ' ' || COALESCE(p.last_name, '')) AS patient_name,
           p.uhid AS patient_uhid,
           d.full_name AS doctor_name
    FROM public.beds b
    LEFT JOIN public.admissions a ON a.bed_id = b.id AND a.status = 'admitted'
    LEFT JOIN public.patients p ON p.id = a.patient_id
    LEFT JOIN public.doctors  d ON d.id = a.attending_doctor_id
"""


async def list_beds(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch(
        f"{_BED_BASE} WHERE b.is_active = true ORDER BY b.room_no, b.bed_label"
    )
    return [dict(r) for r in rows]


async def get_bed(conn: asyncpg.Connection, bed_id: int) -> dict:
    row = await conn.fetchrow(f"{_BED_BASE} WHERE b.id = $1", bed_id)
    if row is None:
        raise AppError("NOT_FOUND", "Bed not found.", status_code=404)
    return dict(row)


async def admit(
    conn: asyncpg.Connection, data: AdmissionCreate, actor_id: str
) -> dict:
    if not await conn.fetchval(
        "SELECT 1 FROM public.patients WHERE id = $1", data.patient_id
    ):
        raise AppError("NOT_FOUND", "Patient not found.", status_code=404)

    # Lock the bed row so two admissions can't race for it.
    bed = await conn.fetchrow(
        "SELECT status FROM public.beds WHERE id = $1 FOR UPDATE", data.bed_id
    )
    if bed is None:
        raise AppError("NOT_FOUND", "Bed not found.", status_code=404)
    if bed["status"] != "available":
        raise AppError("BED_UNAVAILABLE", "That bed is not available.",
                       status_code=409)

    row = await conn.fetchrow(
        """
        INSERT INTO public.admissions
            (patient_id, bed_id, attending_doctor_id, diagnosis, created_by)
        VALUES ($1, $2, $3, $4, $5::uuid)
        RETURNING id
        """,
        data.patient_id, data.bed_id, data.attending_doctor_id,
        data.diagnosis, actor_id,
    )
    await conn.execute(
        "UPDATE public.beds SET status = 'occupied' WHERE id = $1", data.bed_id
    )
    await write_audit(conn, actor_id=actor_id, action="admit",
                      entity="admissions", entity_id=row["id"],
                      detail={"bed_id": data.bed_id, "patient_id": data.patient_id})
    return await get_bed(conn, data.bed_id)


async def transfer(
    conn: asyncpg.Connection, admission_id: int, data: TransferRequest, actor_id: str
) -> dict:
    adm = await conn.fetchrow(
        "SELECT bed_id, status FROM public.admissions WHERE id = $1", admission_id
    )
    if adm is None:
        raise AppError("NOT_FOUND", "Admission not found.", status_code=404)
    if adm["status"] != "admitted":
        raise AppError("NOT_ADMITTED", "This patient is not currently admitted.",
                       status_code=422)
    if data.to_bed_id == adm["bed_id"]:
        raise AppError("SAME_BED", "Choose a different bed.", status_code=422)

    to_bed = await conn.fetchrow(
        "SELECT status FROM public.beds WHERE id = $1 FOR UPDATE", data.to_bed_id
    )
    if to_bed is None:
        raise AppError("NOT_FOUND", "Target bed not found.", status_code=404)
    if to_bed["status"] != "available":
        raise AppError("BED_UNAVAILABLE", "The target bed is not available.",
                       status_code=409)

    await conn.execute("UPDATE public.beds SET status = 'available' WHERE id = $1",
                       adm["bed_id"])
    await conn.execute("UPDATE public.beds SET status = 'occupied' WHERE id = $1",
                       data.to_bed_id)
    await conn.execute("UPDATE public.admissions SET bed_id = $1 WHERE id = $2",
                       data.to_bed_id, admission_id)
    await write_audit(conn, actor_id=actor_id, action="transfer",
                      entity="admissions", entity_id=admission_id,
                      detail={"from_bed": adm["bed_id"], "to_bed": data.to_bed_id})
    return await get_bed(conn, data.to_bed_id)


async def discharge(
    conn: asyncpg.Connection, admission_id: int, data: DischargeRequest, actor_id: str
) -> dict:
    adm = await conn.fetchrow(
        "SELECT bed_id, status FROM public.admissions WHERE id = $1", admission_id
    )
    if adm is None:
        raise AppError("NOT_FOUND", "Admission not found.", status_code=404)
    if adm["status"] != "admitted":
        raise AppError("NOT_ADMITTED", "This patient is not currently admitted.",
                       status_code=422)

    await conn.execute(
        "UPDATE public.admissions SET status = 'discharged', discharged_at = now(), "
        "discharge_summary = $1 WHERE id = $2",
        data.discharge_summary, admission_id,
    )
    await conn.execute("UPDATE public.beds SET status = 'available' WHERE id = $1",
                       adm["bed_id"])
    await write_audit(conn, actor_id=actor_id, action="discharge",
                      entity="admissions", entity_id=admission_id)
    return await get_bed(conn, adm["bed_id"])
