"""OPD session + token-queue business logic.

Token numbers are assigned at check-in, in arrival order, sequential per
doctor per day. The unique index uq_queue_token guards against duplicates.
"""

from __future__ import annotations

from datetime import date

import asyncpg

from ..errors import AppError
from ..schemas.queue import QueueAdd, QueueStatusUpdate, SessionUpsert
from ..utils.audit import write_audit

_QUEUE_SELECT = """
    SELECT q.id, q.doctor_id, q.patient_id, q.queue_date, q.token_no, q.status,
           q.reason, q.booked_at, q.checked_in_at, q.called_at, q.completed_at,
           p.uhid AS patient_uhid,
           (p.first_name || ' ' || COALESCE(p.last_name, '')) AS patient_name,
           p.phone AS patient_phone, p.dob AS patient_dob, p.gender AS patient_gender,
           d.full_name AS doctor_name
    FROM public.queue_entries q
    JOIN public.patients p ON p.id = q.patient_id
    JOIN public.doctors  d ON d.id = q.doctor_id
"""


# ------------------------- doctors -------------------------
async def list_doctors(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch(
        "SELECT id, full_name, specialty, consult_fee, covers_for_doctor_id "
        "FROM public.doctors WHERE is_active = true ORDER BY full_name"
    )
    return [dict(r) for r in rows]


# ------------------------- sessions -------------------------
async def list_sessions(
    conn: asyncpg.Connection, day: date, doctor_id: int | None
) -> list[dict]:
    params: list = [day]
    where = "WHERE s.session_date = $1"
    if doctor_id is not None:
        params.append(doctor_id)
        where += " AND s.doctor_id = $2"
    rows = await conn.fetch(
        f"""
        SELECT s.id, s.doctor_id, s.session_date, s.start_time, s.end_time,
               d.full_name AS doctor_name
        FROM public.opd_sessions s
        JOIN public.doctors d ON d.id = s.doctor_id
        {where}
        ORDER BY s.start_time
        """,
        *params,
    )
    return [dict(r) for r in rows]


async def upsert_session(
    conn: asyncpg.Connection, data: SessionUpsert, actor_id: str
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO public.opd_sessions
            (doctor_id, session_date, start_time, end_time, created_by)
        VALUES ($1, $2, $3, $4, $5::uuid)
        ON CONFLICT (doctor_id, session_date) DO UPDATE
            SET start_time = EXCLUDED.start_time,
                end_time   = EXCLUDED.end_time,
                updated_at = now()
        RETURNING id, doctor_id, session_date, start_time, end_time
        """,
        data.doctor_id,
        data.session_date,
        data.start_time,
        data.end_time,
        actor_id,
    )
    await write_audit(
        conn, actor_id=actor_id, action="upsert", entity="opd_sessions",
        entity_id=row["id"],
    )
    return dict(row)


# ------------------------- queue -------------------------
async def _next_token(conn: asyncpg.Connection, doctor_id: int, day: date) -> int:
    return await conn.fetchval(
        "SELECT COALESCE(MAX(token_no), 0) + 1 FROM public.queue_entries "
        "WHERE doctor_id = $1 AND queue_date = $2",
        doctor_id,
        day,
    )


async def get_by_id(conn: asyncpg.Connection, entry_id: int) -> dict:
    row = await conn.fetchrow(f"{_QUEUE_SELECT} WHERE q.id = $1", entry_id)
    if row is None:
        raise AppError("NOT_FOUND", "Queue entry not found.", status_code=404)
    return dict(row)


async def list_queue(
    conn: asyncpg.Connection, day: date, doctor_id: int | None
) -> list[dict]:
    params: list = [day]
    where = "WHERE q.queue_date = $1 AND q.status <> 'cancelled'"
    if doctor_id is not None:
        # A covering doctor (e.g. Pallavi) also sees the covered doctor's
        # (Hetal's) patients — but not the other way around.
        cover = await conn.fetchval(
            "SELECT covers_for_doctor_id FROM public.doctors WHERE id = $1",
            doctor_id,
        )
        ids = [doctor_id] + ([cover] if cover else [])
        params.append(ids)
        where += " AND q.doctor_id = ANY($2::bigint[])"
    rows = await conn.fetch(
        f"{_QUEUE_SELECT} {where} ORDER BY q.token_no ASC NULLS LAST, q.booked_at",
        *params,
    )
    return [dict(r) for r in rows]


async def add(conn: asyncpg.Connection, data: QueueAdd, actor_id: str) -> dict:
    if not await conn.fetchval(
        "SELECT 1 FROM public.patients WHERE id = $1", data.patient_id
    ):
        raise AppError("NOT_FOUND", "Patient not found.", status_code=404)
    if not await conn.fetchval(
        "SELECT 1 FROM public.doctors WHERE id = $1 AND is_active = true",
        data.doctor_id,
    ):
        raise AppError("NOT_FOUND", "Doctor not found.", status_code=404)

    token = None
    status = "booked"
    checked_in = None
    if data.check_in:
        token = await _next_token(conn, data.doctor_id, data.queue_date)
        status = "waiting"
        checked_in = "now()"

    row = await conn.fetchrow(
        f"""
        INSERT INTO public.queue_entries
            (doctor_id, patient_id, queue_date, token_no, status, reason,
             checked_in_at, created_by)
        VALUES ($1, $2, $3, $4, $5, $6, {'now()' if checked_in else 'NULL'}, $7::uuid)
        RETURNING id
        """,
        data.doctor_id,
        data.patient_id,
        data.queue_date,
        token,
        status,
        data.reason,
        actor_id,
    )
    await write_audit(
        conn, actor_id=actor_id, action="create", entity="queue_entries",
        entity_id=row["id"], detail={"status": status},
    )
    return await get_by_id(conn, row["id"])


async def update_status(
    conn: asyncpg.Connection,
    entry_id: int,
    data: QueueStatusUpdate,
    actor_id: str,
) -> dict:
    row = await conn.fetchrow(
        "SELECT doctor_id, queue_date, token_no FROM public.queue_entries "
        "WHERE id = $1",
        entry_id,
    )
    if row is None:
        raise AppError("NOT_FOUND", "Queue entry not found.", status_code=404)

    sets = ["status = $1"]
    params: list = [data.status]
    new_status = data.status

    # Checking in (booked -> waiting): assign a token and timestamp.
    if new_status == "waiting" and row["token_no"] is None:
        token = await _next_token(conn, row["doctor_id"], row["queue_date"])
        params.append(token)
        sets.append(f"token_no = ${len(params)}")
        sets.append("checked_in_at = COALESCE(checked_in_at, now())")
    elif new_status == "in_consultation":
        sets.append("called_at = COALESCE(called_at, now())")
    elif new_status == "completed":
        sets.append("completed_at = now()")

    params.append(entry_id)
    await conn.execute(
        f"UPDATE public.queue_entries SET {', '.join(sets)} WHERE id = ${len(params)}",
        *params,
    )
    await write_audit(
        conn, actor_id=actor_id, action="update", entity="queue_entries",
        entity_id=entry_id, detail={"status": new_status},
    )
    return await get_by_id(conn, entry_id)
