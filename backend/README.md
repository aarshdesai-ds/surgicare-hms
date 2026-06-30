# HMS Backend (FastAPI + Supabase)

Day 1 foundation: app scaffold, Supabase JWT auth, error envelope, structured
logging, health checks, and the core database schema with Row-Level Security.

## Prerequisites
- Python 3.11+
- A Supabase project (free tier is fine). Choose the **Mumbai (ap-south-1)** region.

## 1. Install (Windows PowerShell)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Configure
```powershell
Copy-Item .env.example .env
```
Fill in `.env` from your Supabase dashboard:
- `DATABASE_URL` — Settings → Database → Connection string (URI). Use the **Session pooler** URI.
- `SUPABASE_JWT_SECRET` — Settings → API → JWT Settings → JWT Secret.
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` — Settings → API.

## 3. Apply database migrations
Open the Supabase **SQL Editor** and run, in order:
1. `migrations/001_init.sql`  (extensions, profiles, doctors, patients, audit_log)
2. `migrations/002_rls.sql`   (Row-Level Security policies)

> The `profiles` row for each user is created automatically on signup by a
> trigger. To make a user an **admin**, set their role:
> ```sql
> update public.profiles set role = 'admin' where id = '<auth-user-uuid>';
> ```
> The role is read from `app_metadata.role` in the JWT for API authorization —
> set it via the Supabase Auth admin API, or keep `profiles.role` as the source
> of truth and mirror it into `app_metadata` (added in a later day).

## 4. Run
```powershell
uvicorn app.main:app --reload
```
- API docs (auto-generated): http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/healthz
- Readiness: http://127.0.0.1:8000/readyz

## 5. Test
```powershell
pytest
```
Two tiers:
- **Unit / API tests** (always run, no DB): schema validation, JWT auth, RBAC
  (`require_roles`), and the error envelope.
- **Integration tests** (skipped unless `TEST_DATABASE_URL` is set): exercise the
  service layer against real Postgres — UHID + duplicate detection, token
  sequencing & check-in, doctor coverage (one-way), encounters, OT ordering.
  Each runs in a **rolled-back transaction**, so no data is persisted.

To include the integration tests, point `TEST_DATABASE_URL` at a Postgres DB
(your Supabase URL works) and run pytest:
```powershell
$env:TEST_DATABASE_URL = "<your DATABASE_URL>"
pytest
```
> Note: UHID/identity sequences are non-transactional, so their counters advance
> even though rows are rolled back (harmless).

## What exists after Day 1
| Area | Status |
|---|---|
| FastAPI app factory, CORS, request-id logging | ✅ |
| Supabase JWT verification + `require_roles(...)` RBAC | ✅ |
| Consistent error envelope + handlers | ✅ |
| `/healthz`, `/readyz`, `/api/me` | ✅ |
| Schema: profiles, doctors, patients, audit_log | ✅ |
| RLS policies | ✅ |
| Tests (pytest) | ✅ |

## Next (Day 1 cont. / Day 2)
- React UI shell designed with Claude (layout, language toggle, Supabase login).
- Then **Feature 1: Patient registration & search** (Days 3–5).

## Project layout
```
backend/
  app/
    main.py            # app factory, middleware, lifespan
    config.py          # env settings (pydantic-settings)
    database.py        # asyncpg pool (graceful degradation)
    auth.py            # Supabase JWT verify + require_roles RBAC
    errors.py          # AppError + error-envelope handlers
    logging_config.py  # structlog setup
    routers/
      health.py        # /healthz, /readyz, /api/me
  migrations/
    001_init.sql
    002_rls.sql
  tests/
    test_health.py
  requirements.txt
  .env.example
```
