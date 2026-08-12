"""Dashboard summary aggregation for a given day."""

from __future__ import annotations

from datetime import date

import asyncpg

_EMPTY = {
    "booked": 0, "waiting": 0, "in_consultation": 0,
    "completed": 0, "no_show": 0, "total": 0, "current_token": None,
}

# A waiting patient past this many minutes is surfaced in "Attention needed".
# Tunable to match the hospital's own sense of an acceptable OPD wait.
WAIT_ALERT_MIN = 30


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

    # Live wait times only make sense for the current day. For a past date the
    # clock has moved on, so "minutes waiting" would be meaningless.
    today_ist = await conn.fetchval("SELECT (now() AT TIME ZONE 'Asia/Kolkata')::date")
    attention: list[dict] = []
    waiting_longest = 0
    if day == today_ist:
        name_by_doc = {d["id"]: d["full_name"] for d in doctors}
        waits = await conn.fetch(
            "SELECT q.token_no, q.doctor_id, "
            "       p.first_name, p.last_name, "
            "       floor(EXTRACT(EPOCH FROM (now() - q.checked_in_at)) / 60)::int AS wait_min "
            "FROM public.queue_entries q "
            "JOIN public.patients p ON p.id = q.patient_id "
            "WHERE q.queue_date = $1 AND q.status = 'waiting' "
            "  AND q.checked_in_at IS NOT NULL "
            "ORDER BY q.checked_in_at ASC",
            day,
        )
        for w in waits:
            wait_min = max(0, w["wait_min"] or 0)
            waiting_longest = max(waiting_longest, wait_min)
            if wait_min >= WAIT_ALERT_MIN:
                full = f'{w["first_name"] or ""} {w["last_name"] or ""}'.strip()
                attention.append({
                    "token_no": w["token_no"],
                    "patient_name": full or "—",
                    "doctor_name": name_by_doc.get(w["doctor_id"], "—"),
                    "wait_min": wait_min,
                })
        attention.sort(key=lambda a: a["wait_min"], reverse=True)

    return {
        "date": day.isoformat(),
        "totals": {
            "patients_total": patients_total,
            "registered_today": registered_today,
            "waiting_longest": waiting_longest,
            **totals,
        },
        "attention": attention,
        "wait_alert_min": WAIT_ALERT_MIN,
        "doctors": doctors_out,
    }
