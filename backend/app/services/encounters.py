"""Clinical encounter business logic."""

from __future__ import annotations

import asyncpg

from ..errors import AppError
from ..schemas.encounter import EncounterCreate
from ..utils.audit import write_audit

_SELECT = """
    SELECT e.id, e.patient_id, e.doctor_id, e.queue_entry_id, e.encounter_type,
           e.vitals, e.complaints, e.diagnosis, e.notes, e.occurred_at,
           d.full_name AS doctor_name
    FROM public.encounters e
    LEFT JOIN public.doctors d ON d.id = e.doctor_id
"""


async def get_by_id(conn: asyncpg.Connection, enc_id: int) -> dict:
    row = await conn.fetchrow(f"{_SELECT} WHERE e.id = $1", enc_id)
    if row is None:
        raise AppError("NOT_FOUND", "Encounter not found.", status_code=404)
    return dict(row)


async def list_for_patient(
    conn: asyncpg.Connection, patient_id: int
) -> list[dict]:
    rows = await conn.fetch(
        f"{_SELECT} WHERE e.patient_id = $1 ORDER BY e.occurred_at DESC",
        patient_id,
    )
    return [dict(r) for r in rows]


async def create(
    conn: asyncpg.Connection, data: EncounterCreate, actor_id: str
) -> dict:
    if not await conn.fetchval(
        "SELECT 1 FROM public.patients WHERE id = $1", data.patient_id
    ):
        raise AppError("NOT_FOUND", "Patient not found.", status_code=404)

    row = await conn.fetchrow(
        """
        INSERT INTO public.encounters
            (patient_id, doctor_id, queue_entry_id, encounter_type,
             vitals, complaints, diagnosis, notes, created_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::uuid)
        RETURNING id
        """,
        data.patient_id, data.doctor_id, data.queue_entry_id,
        data.encounter_type, data.vitals, data.complaints,
        data.diagnosis, data.notes, actor_id,
    )
    await write_audit(
        conn, actor_id=actor_id, action="create", entity="encounters",
        entity_id=row["id"], detail={"patient_id": data.patient_id},
    )
    return await get_by_id(conn, row["id"])
