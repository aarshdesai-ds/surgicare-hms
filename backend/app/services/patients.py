"""Patient management business logic.

Kept separate from the HTTP layer so it can be unit-tested and reused. All
functions take an acquired asyncpg connection so the caller controls the
transaction boundary.
"""

from __future__ import annotations

import asyncpg

from ..errors import AppError
from ..schemas.patient import PatientCreate, PatientUpdate
from ..utils.audit import write_audit

# Columns returned for a full patient record.
_FULL_COLUMNS = """
    id, uhid, first_name, last_name, dob, gender, phone, alt_phone,
    address, blood_group, abha_number, emergency_contact, allergies,
    created_at, created_by
"""

# Lighter projection for list/search results.
_LIST_COLUMNS = "id, uhid, first_name, last_name, phone, gender, dob, created_at"


async def find_duplicates(conn: asyncpg.Connection, phone: str) -> list[dict]:
    """Existing patients sharing the same phone number."""
    rows = await conn.fetch(
        f"SELECT {_LIST_COLUMNS} FROM public.patients WHERE phone = $1", phone
    )
    return [dict(r) for r in rows]


async def create(
    conn: asyncpg.Connection,
    data: PatientCreate,
    actor_id: str,
    force: bool = False,
) -> dict:
    """Register a new patient. Raises 409 if a phone duplicate exists and
    `force` is False, returning the matches so the UI can confirm."""
    if not force:
        duplicates = await find_duplicates(conn, data.phone)
        if duplicates:
            raise AppError(
                code="DUPLICATE_PATIENT",
                message="A patient with this phone number already exists.",
                status_code=409,
                fields={"duplicates": duplicates},
            )

    row = await conn.fetchrow(
        f"""
        INSERT INTO public.patients
            (first_name, last_name, dob, gender, phone, alt_phone, address,
             blood_group, abha_number, emergency_contact, allergies, created_by)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::uuid)
        RETURNING {_FULL_COLUMNS}
        """,
        data.first_name,
        data.last_name,
        data.dob,
        data.gender,
        data.phone,
        data.alt_phone,
        data.address,
        data.blood_group,
        data.abha_number,
        data.emergency_contact,
        data.allergies,
        actor_id,
    )
    patient = dict(row)
    await write_audit(
        conn,
        actor_id=actor_id,
        action="create",
        entity="patients",
        entity_id=patient["id"],
        detail={"uhid": patient["uhid"]},
    )
    return patient


async def search(
    conn: asyncpg.Connection, q: str, limit: int, offset: int
) -> tuple[list[dict], int]:
    """Search by UHID, phone, or name. Returns (items, total)."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    where = ""
    params: list = []
    if q:
        params.append(f"%{q.strip()}%")
        where = (
            "WHERE uhid ILIKE $1 OR phone ILIKE $1 "
            "OR (first_name || ' ' || COALESCE(last_name, '')) ILIKE $1"
        )

    total = await conn.fetchval(
        f"SELECT COUNT(*) FROM public.patients {where}", *params
    )
    rows = await conn.fetch(
        f"""
        SELECT {_LIST_COLUMNS} FROM public.patients {where}
        ORDER BY created_at DESC
        LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
        """,
        *params,
        limit,
        offset,
    )
    return [dict(r) for r in rows], int(total)


async def get_by_id(
    conn: asyncpg.Connection, patient_id: int, actor_id: str
) -> dict:
    row = await conn.fetchrow(
        f"SELECT {_FULL_COLUMNS} FROM public.patients WHERE id = $1", patient_id
    )
    if row is None:
        raise AppError("NOT_FOUND", "Patient not found.", status_code=404)
    # Accessing a full patient record is PHI access — record it.
    await write_audit(
        conn,
        actor_id=actor_id,
        action="view_phi",
        entity="patients",
        entity_id=patient_id,
    )
    return dict(row)


async def update(
    conn: asyncpg.Connection,
    patient_id: int,
    data: PatientUpdate,
    actor_id: str,
) -> dict:
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        raise AppError("VALIDATION_ERROR", "No fields to update.", status_code=400)

    exists = await conn.fetchval(
        "SELECT 1 FROM public.patients WHERE id = $1", patient_id
    )
    if not exists:
        raise AppError("NOT_FOUND", "Patient not found.", status_code=404)

    set_parts = []
    params: list = []
    for i, (col, val) in enumerate(fields.items(), start=1):
        set_parts.append(f"{col} = ${i}")
        params.append(val)
    params.append(patient_id)

    row = await conn.fetchrow(
        f"""
        UPDATE public.patients SET {', '.join(set_parts)}
        WHERE id = ${len(params)}
        RETURNING {_FULL_COLUMNS}
        """,
        *params,
    )
    await write_audit(
        conn,
        actor_id=actor_id,
        action="update",
        entity="patients",
        entity_id=patient_id,
        detail={"changed": list(fields.keys())},
    )
    return dict(row)
