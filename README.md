# SurgiCare Hospital — Management System

Operational management software for **SurgiCare Hospital, Valsad**: patients,
OPD token-queue, operation-theatre scheduling, consultation notes, and a live
dashboard. Bilingual (English / ગુજરાતી).

> Logistics-focused MVP — **not** clinical decision support.

## Stack
- **Frontend:** React + Vite, `react-i18next` (static EN/Gujarati catalogs)
- **Backend:** FastAPI (Python), asyncpg
- **Database / Auth:** Supabase (Postgres + Auth + Row-Level Security), Mumbai region
- **Payments (planned):** Razorpay (UPI/GPay)

## Features
- **Patients** — registration with auto-UHID, duplicate detection, search, profile, audit log
- **OPD queue** — per-doctor daily sessions; walk-in / pre-book; tokens assigned at check-in; status workflow
- **Doctor coverage** — Dr. Pallavi covers Dr. Hetal's patients (one-way), in the queue and OT
- **Operation theatres** — ordered daily case lists per theatre, reorder, status workflow, surgeon filter
- **Consultation notes** — vitals + complaints + diagnosis + notes per visit; visit history on the patient
- **Dashboard** — live daily stats per doctor (IST-correct)

## Repo layout
```
backend/    FastAPI app, migrations (run in Supabase SQL editor), pytest suite
frontend/   React + Vite app
.github/    GitHub Actions CI
```

## Getting started
- Backend: see [backend/README.md](backend/README.md)
- Frontend: see [frontend/README.md](frontend/README.md)
- Apply `backend/migrations/*.sql` in order via the Supabase SQL editor.

## Testing
```bash
cd backend && pytest
```
Unit/API tests run with no setup. Integration tests run when `TEST_DATABASE_URL`
is set (each runs in a rolled-back transaction). CI runs the backend tests and a
frontend build on every push — see [.github/workflows/ci.yml](.github/workflows/ci.yml).
