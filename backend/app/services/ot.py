"""Operation theatre scheduling — daily ordered case lists per theatre."""

from __future__ import annotations

from datetime import date

import asyncpg

from ..errors import AppError
from ..schemas.ot import OTCaseCreate, OTMove, OTStatusUpdate
from ..utils.audit import write_audit

_OT_SELECT = """
    SELECT c.id, c.theatre_id, c.case_date, c.patient_id, c.surgeon_id,
           c.procedure, c.position, c.status, c.notes,
           c.started_at, c.completed_at,
           t.name AS theatre_name,
           p.uhid AS patient_uhid,
           (p.first_name || ' ' || COALESCE(p.last_name, '')) AS patient_name,
           p.phone AS patient_phone,
           d.full_name AS surgeon_name
    FROM public.ot_cases c
    JOIN public.operation_theatres t ON t.id = c.theatre_id
    JOIN public.patients p ON p.id = c.patient_id
    JOIN public.doctors  d ON d.id = c.surgeon_id
"""


async def list_theatres(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch(
        "SELECT id, name, obgyn_only FROM public.operation_theatres "
        "WHERE is_active = true ORDER BY name"
    )
    return [dict(r) for r in rows]


async def get_by_id(conn: asyncpg.Connection, case_id: int) -> dict:
    row = await conn.fetchrow(f"{_OT_SELECT} WHERE c.id = $1", case_id)
    if row is None:
        raise AppError("NOT_FOUND", "OT case not found.", status_code=404)
    return dict(row)


async def list_cases(
    conn: asyncpg.Connection,
    day: date,
    theatre_id: int | None,
    surgeon_id: int | None = None,
) -> list[dict]:
    params: list = [day]
    where = "WHERE c.case_date = $1 AND c.status <> 'cancelled'"
    if theatre_id is not None:
        params.append(theatre_id)
        where += f" AND c.theatre_id = ${len(params)}"
    if surgeon_id is not None:
        # A covering surgeon (Pallavi) also sees the covered surgeon's (Hetal's)
        # cases — but not vice-versa.
        cover = await conn.fetchval(
            "SELECT covers_for_doctor_id FROM public.doctors WHERE id = $1",
            surgeon_id,
        )
        ids = [surgeon_id] + ([cover] if cover else [])
        params.append(ids)
        where += f" AND c.surgeon_id = ANY(${len(params)}::bigint[])"
    rows = await conn.fetch(
        f"{_OT_SELECT} {where} ORDER BY c.theatre_id, c.position", *params
    )
    return [dict(r) for r in rows]


async def add(conn: asyncpg.Connection, data: OTCaseCreate, actor_id: str) -> dict:
    if not await conn.fetchval(
        "SELECT 1 FROM public.patients WHERE id = $1", data.patient_id
    ):
        raise AppError("NOT_FOUND", "Patient not found.", status_code=404)
    surgeon = await conn.fetchrow(
        "SELECT specialty FROM public.doctors WHERE id = $1 AND is_active = true",
        data.surgeon_id,
    )
    if surgeon is None:
        raise AppError("NOT_FOUND", "Surgeon not found.", status_code=404)
    theatre = await conn.fetchrow(
        "SELECT name, obgyn_only FROM public.operation_theatres WHERE id = $1",
        data.theatre_id,
    )
    if theatre is None:
        raise AppError("NOT_FOUND", "Theatre not found.", status_code=404)
    # Labor Room is for obstetrics & gynaecology surgeons only.
    if theatre["obgyn_only"] and surgeon["specialty"] != "obgyn":
        raise AppError(
            "THEATRE_RESTRICTED",
            f"The {theatre['name']} is for obstetrics & gynaecology surgeons only.",
            status_code=422,
        )

    position = await conn.fetchval(
        "SELECT COALESCE(MAX(position), 0) + 1 FROM public.ot_cases "
        "WHERE theatre_id = $1 AND case_date = $2",
        data.theatre_id,
        data.case_date,
    )
    row = await conn.fetchrow(
        """
        INSERT INTO public.ot_cases
            (theatre_id, case_date, patient_id, surgeon_id, procedure,
             position, notes, created_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::uuid)
        RETURNING id
        """,
        data.theatre_id, data.case_date, data.patient_id, data.surgeon_id,
        data.procedure, position, data.notes, actor_id,
    )
    await write_audit(
        conn, actor_id=actor_id, action="create", entity="ot_cases",
        entity_id=row["id"],
    )
    return await get_by_id(conn, row["id"])


async def update_status(
    conn: asyncpg.Connection, case_id: int, data: OTStatusUpdate, actor_id: str
) -> dict:
    if not await conn.fetchval(
        "SELECT 1 FROM public.ot_cases WHERE id = $1", case_id
    ):
        raise AppError("NOT_FOUND", "OT case not found.", status_code=404)

    sets = ["status = $1"]
    if data.status == "in_progress":
        sets.append("started_at = COALESCE(started_at, now())")
    elif data.status == "completed":
        sets.append("completed_at = now()")

    await conn.execute(
        f"UPDATE public.ot_cases SET {', '.join(sets)} WHERE id = $2",
        data.status, case_id,
    )
    await write_audit(
        conn, actor_id=actor_id, action="update", entity="ot_cases",
        entity_id=case_id, detail={"status": data.status},
    )
    return await get_by_id(conn, case_id)


async def move(
    conn: asyncpg.Connection, case_id: int, data: OTMove, actor_id: str
) -> dict:
    cur = await conn.fetchrow(
        "SELECT theatre_id, case_date, position FROM public.ot_cases WHERE id = $1",
        case_id,
    )
    if cur is None:
        raise AppError("NOT_FOUND", "OT case not found.", status_code=404)

    if data.direction == "up":
        neighbor = await conn.fetchrow(
            "SELECT id, position FROM public.ot_cases "
            "WHERE theatre_id = $1 AND case_date = $2 AND position < $3 "
            "ORDER BY position DESC LIMIT 1",
            cur["theatre_id"], cur["case_date"], cur["position"],
        )
    else:
        neighbor = await conn.fetchrow(
            "SELECT id, position FROM public.ot_cases "
            "WHERE theatre_id = $1 AND case_date = $2 AND position > $3 "
            "ORDER BY position ASC LIMIT 1",
            cur["theatre_id"], cur["case_date"], cur["position"],
        )
    if neighbor is not None:  # already at an edge -> no-op
        await conn.execute(
            "UPDATE public.ot_cases SET position = $1 WHERE id = $2",
            neighbor["position"], case_id,
        )
        await conn.execute(
            "UPDATE public.ot_cases SET position = $1 WHERE id = $2",
            cur["position"], neighbor["id"],
        )
    return await get_by_id(conn, case_id)
