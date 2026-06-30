"""End-of-day report aggregation for a given date (IST)."""

from __future__ import annotations

from datetime import date

import asyncpg

_OPD_STATUSES = (
    "booked", "waiting", "in_consultation", "completed", "no_show", "cancelled",
)


async def day_report(conn: asyncpg.Connection, day: date) -> dict:
    # New patient registrations on this IST calendar day.
    regs = await conn.fetch(
        """
        SELECT uhid,
               (first_name || ' ' || COALESCE(last_name, '')) AS name,
               phone, created_at
        FROM public.patients
        WHERE (created_at AT TIME ZONE 'Asia/Kolkata')::date = $1
        ORDER BY created_at
        """,
        day,
    )

    opd = await conn.fetch(
        """
        SELECT q.doctor_id, q.status, d.full_name AS doctor_name, d.specialty
        FROM public.queue_entries q
        JOIN public.doctors d ON d.id = q.doctor_id
        WHERE q.queue_date = $1
        """,
        day,
    )

    ot = await conn.fetch(
        """
        SELECT c.position, c.status, c.procedure,
               t.name AS theatre_name,
               (p.first_name || ' ' || COALESCE(p.last_name, '')) AS patient_name,
               p.uhid AS patient_uhid,
               d.full_name AS surgeon_name
        FROM public.ot_cases c
        JOIN public.operation_theatres t ON t.id = c.theatre_id
        JOIN public.patients p ON p.id = c.patient_id
        JOIN public.doctors  d ON d.id = c.surgeon_id
        WHERE c.case_date = $1
        ORDER BY t.name, c.position
        """,
        day,
    )

    enc_count = await conn.fetchval(
        "SELECT COUNT(*) FROM public.encounters "
        "WHERE (occurred_at AT TIME ZONE 'Asia/Kolkata')::date = $1",
        day,
    )

    # --- OPD aggregation per doctor ---
    per_doc: dict = {}
    opd_tot = {s: 0 for s in _OPD_STATUSES}
    opd_tot["total"] = 0
    for r in opd:
        d = per_doc.setdefault(
            r["doctor_id"],
            {"doctor_name": r["doctor_name"], "specialty": r["specialty"],
             **{s: 0 for s in _OPD_STATUSES}, "total": 0},
        )
        st = r["status"]
        d[st] = d.get(st, 0) + 1
        d["total"] += 1
        opd_tot[st] += 1
        opd_tot["total"] += 1

    # --- OT aggregation ---
    ot_tot = {"total": 0, "completed": 0, "cancelled": 0,
              "scheduled": 0, "in_progress": 0}
    for r in ot:
        ot_tot["total"] += 1
        if r["status"] in ot_tot:
            ot_tot[r["status"]] += 1

    return {
        "date": day.isoformat(),
        "registrations": {
            "count": len(regs),
            "items": [dict(r) for r in regs],
        },
        "opd": {
            "totals": opd_tot,
            "by_doctor": [{"doctor_id": k, **v} for k, v in per_doc.items()],
        },
        "ot": {
            "totals": ot_tot,
            "cases": [dict(r) for r in ot],
        },
        "encounters": {"count": int(enc_count)},
    }
