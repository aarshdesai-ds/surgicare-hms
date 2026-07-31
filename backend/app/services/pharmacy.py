"""Prescriptions + pharmacy outbox (delivery to Visual Chemist).

Creating a prescription freezes a standard JSON payload into pharmacy_outbox
with status 'pending'. A PharmacyAdapter (see integrations/pharmacy_adapter.py)
delivers pending items via whatever transport the vendor supports; until that's
configured, staff pull the payload / print the Rx and mark it sent.
"""

from __future__ import annotations

from datetime import datetime, timezone

import asyncpg

from ..errors import AppError
from ..schemas.prescription import PrescriptionCreate
from ..utils.audit import write_audit

_HEADER = """
    SELECT r.id, r.patient_id, r.doctor_id, r.encounter_id, r.notes, r.created_at,
           p.uhid AS patient_uhid,
           (p.first_name || ' ' || COALESCE(p.last_name, '')) AS patient_name,
           p.phone AS patient_phone, p.dob, p.gender,
           d.full_name AS doctor_name, d.specialty AS doctor_specialty
    FROM public.prescriptions r
    JOIN public.patients p ON p.id = r.patient_id
    LEFT JOIN public.doctors d ON d.id = r.doctor_id
"""


async def _items(conn: asyncpg.Connection, rx_id: int) -> list[dict]:
    rows = await conn.fetch(
        "SELECT drug_name, strength, frequency, duration, quantity, instructions "
        "FROM public.prescription_items WHERE prescription_id = $1 ORDER BY position",
        rx_id,
    )
    return [dict(r) for r in rows]


async def _build_payload(conn: asyncpg.Connection, rx_id: int) -> dict:
    """Standard export snapshot the pharmacy consumes."""
    h = await conn.fetchrow(f"{_HEADER} WHERE r.id = $1", rx_id)
    items = await _items(conn, rx_id)
    return {
        "source": "SurgiCare HMS",
        "prescription_id": rx_id,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "patient": {
            "uhid": h["patient_uhid"], "name": h["patient_name"].strip(),
            "phone": h["patient_phone"],
            "dob": h["dob"].isoformat() if h["dob"] else None,
            "gender": h["gender"],
        },
        "doctor": {"name": h["doctor_name"], "specialty": h["doctor_specialty"]},
        "notes": h["notes"],
        "items": items,
    }


async def create(
    conn: asyncpg.Connection, data: PrescriptionCreate, actor_id: str
) -> dict:
    if not await conn.fetchval(
        "SELECT 1 FROM public.patients WHERE id = $1", data.patient_id
    ):
        raise AppError("NOT_FOUND", "Patient not found.", status_code=404)

    row = await conn.fetchrow(
        "INSERT INTO public.prescriptions (patient_id, doctor_id, encounter_id, "
        "notes, created_by) VALUES ($1, $2, $3, $4, $5::uuid) RETURNING id",
        data.patient_id, data.doctor_id, data.encounter_id, data.notes, actor_id,
    )
    rx_id = row["id"]
    for i, item in enumerate(data.items, start=1):
        await conn.execute(
            """
            INSERT INTO public.prescription_items
                (prescription_id, position, drug_name, strength, frequency,
                 duration, quantity, instructions)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            rx_id, i, item.drug_name, item.strength, item.frequency,
            item.duration, item.quantity, item.instructions,
        )

    # Freeze the export snapshot and queue it for the pharmacy.
    payload = await _build_payload(conn, rx_id)
    await conn.execute(
        "INSERT INTO public.pharmacy_outbox (prescription_id, payload) "
        "VALUES ($1, $2)",
        rx_id, payload,
    )
    await write_audit(conn, actor_id=actor_id, action="prescribe",
                      entity="prescriptions", entity_id=rx_id,
                      detail={"items": len(data.items)})
    return await get_by_id(conn, rx_id)


async def get_by_id(conn: asyncpg.Connection, rx_id: int) -> dict:
    h = await conn.fetchrow(f"{_HEADER} WHERE r.id = $1", rx_id)
    if h is None:
        raise AppError("NOT_FOUND", "Prescription not found.", status_code=404)
    status = await conn.fetchval(
        "SELECT status FROM public.pharmacy_outbox WHERE prescription_id = $1", rx_id
    )
    result = dict(h)
    result["items"] = await _items(conn, rx_id)
    result["pharmacy_status"] = status
    return result


async def list_for_patient(conn: asyncpg.Connection, patient_id: int) -> list[dict]:
    heads = await conn.fetch(
        f"{_HEADER} WHERE r.patient_id = $1 ORDER BY r.created_at DESC", patient_id
    )
    out = []
    for h in heads:
        d = dict(h)
        d["items"] = await _items(conn, h["id"])
        d["pharmacy_status"] = await conn.fetchval(
            "SELECT status FROM public.pharmacy_outbox WHERE prescription_id = $1",
            h["id"],
        )
        out.append(d)
    return out


# ---- pharmacy outbox ----
async def list_outbox(conn: asyncpg.Connection, status: str) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT o.id, o.prescription_id, o.status, o.payload, o.created_at, o.sent_at,
               (p.first_name || ' ' || COALESCE(p.last_name, '')) AS patient_name,
               p.uhid AS patient_uhid, d.full_name AS doctor_name
        FROM public.pharmacy_outbox o
        JOIN public.prescriptions r ON r.id = o.prescription_id
        JOIN public.patients p ON p.id = r.patient_id
        LEFT JOIN public.doctors d ON d.id = r.doctor_id
        WHERE o.status = $1
        ORDER BY o.created_at
        """,
        status,
    )
    return [dict(r) for r in rows]


async def mark_sent(conn: asyncpg.Connection, outbox_id: int, actor_id: str) -> dict:
    row = await conn.fetchrow(
        "UPDATE public.pharmacy_outbox SET status = 'sent', sent_at = now() "
        "WHERE id = $1 RETURNING prescription_id",
        outbox_id,
    )
    if row is None:
        raise AppError("NOT_FOUND", "Outbox entry not found.", status_code=404)
    await write_audit(conn, actor_id=actor_id, action="pharmacy_sent",
                      entity="pharmacy_outbox", entity_id=outbox_id)
    return {"id": outbox_id, "status": "sent"}
