"""Dashboard summary aggregation for a given day."""

from __future__ import annotations

from datetime import date

import asyncpg

_EMPTY = {
    "booked": 0, "waiting": 0, "in_consultation": 0,
    "completed": 0, "no_show": 0, "total": 0, "current_token": None,
}


async def summary(conn: asyncpg.Connection, day: date) -> dict:
    patients_total = await conn.fetchval("SELECT COUNT(*) FROM public.patients")

    # "Today" by the hospital's local calendar (IST), not UTC.
    registered_today = await conn.fetchval(
        "SELECT COUNT(*) FROM public.patients "
        "WHERE (created_at AT TIME ZONE 'Asia/Kolkata')::date = $1",
        day,
    )

    doctors = await conn.fetch(
        "SELECT id, full_name, specialty FROM public.doctors "
        "WHERE is_active = true ORDER BY full_name"
    )
    sessions = await conn.fetch(
        "SELECT doctor_id, start_time, end_time FROM public.opd_sessions "
        "WHERE session_date = $1",
        day,
    )
    session_map = {r["doctor_id"]: r for r in sessions}

    rows = await conn.fetch(
        "SELECT doctor_id, status, token_no FROM public.queue_entries "
        "WHERE queue_date = $1 AND status <> 'cancelled'",
        day,
    )

    per_doc: dict[int, dict] = {}
    totals = {
        "queue_total": 0, "waiting": 0, "in_consultation": 0,
        "completed": 0, "booked": 0, "no_show": 0,
    }
    for r in rows:
        d = per_doc.setdefault(r["doctor_id"], dict(_EMPTY))
        st = r["status"]
        if st in d:
            d[st] += 1
        d["total"] += 1
        if st == "in_consultation":
            d["current_token"] = r["token_no"]
        if st in totals:
            totals[st] += 1
        totals["queue_total"] += 1

    doctors_out = []
    for doc in doctors:
        counts = per_doc.get(doc["id"], dict(_EMPTY))
        s = session_map.get(doc["id"])
        doctors_out.append({
            "doctor_id": doc["id"],
            "doctor_name": doc["full_name"],
            "specialty": doc["specialty"],
            "session": (
                {"start_time": s["start_time"], "end_time": s["end_time"]}
                if s else None
            ),
            "counts": counts,
        })

    return {
        "date": day.isoformat(),
        "totals": {
            "patients_total": patients_total,
            "registered_today": registered_today,
            **totals,
        },
        "doctors": doctors_out,
    }
