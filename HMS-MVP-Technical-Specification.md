# Hospital Management System (HMS) — MVP Technical Specification & Implementation Roadmap

**Facility profile:** Small private hospital, India. Inpatient beds + 2 surgical theatres (OTs). 2 doctors (1 Orthopedic, 1 OB-GYN). Existing standalone pharmacy software. Staff: mixed Gujarati/English.
**Stack:** React (frontend) · Flask (backend) · PostgreSQL (database).
**Goal:** Production-ready MVP focused on operational logistics — *not* clinical decision support.

---

## 0. Key Decisions & Corrections to the Brief (read first)

Two requirements in the brief, as literally stated, would lead a developer down the wrong path. Both are corrected throughout this spec:

| Brief said | Reality | What this spec uses |
|---|---|---|
| "GPay and UPI APIs for payment processing" | Google Pay / UPI do **not** offer direct merchant integration. RBI requires merchants to route through a licensed **Payment Aggregator (PA-PG)**. | **Razorpay** as the aggregator. It exposes UPI (incl. GPay), cards, netbanking, and **UPI QR / Dynamic QR** through one API. Alternatives: Cashfree, PhonePe PG, Paytm. |
| "Language toggle using Google Translate API" | Runtime machine translation of a fixed UI is slow, costs per-call, leaks PHI to a third party, and **mistranslates medical terms** (unsafe). | **Static i18n catalogs** via `react-i18next` with **human-reviewed Gujarati** strings. Google Translate API used *only once, offline, as an authoring aid* to bootstrap the catalog — never at runtime, never on patient data. |

Everything else in the brief is sound and adopted as-is.

---

## 1. MVP Scope Definition

### Design principle
The hospital runs this with minimal IT support. Every feature in the MVP must reduce a daily manual task (a register, a phone call, a paper bill). Anything that is "nice analytics" or "clinical AI" is deferred. Two doctors and two OTs means scheduling is small but **conflict-sensitive** — the value is in preventing double-bookings and lost bills, not in volume.

### MVP — In Scope (Phase 1 launch)

| Priority | Feature | Why it's in MVP (workflow / business impact) |
|---|---|---|
| P0 | **Patient registration & master index (UHID)** | Every other module references the patient. A unique, de-duplicated patient ID is the foundation. |
| P0 | **Appointment scheduling (2 doctors)** | Replaces the paper appointment book; prevents double-booking; enables OPD flow. |
| P0 | **Billing & invoicing (OPD + IPD)** | Direct revenue impact. Itemized invoices, GST handling, payment status. Biggest source of leakage today. |
| P0 | **Online payment (UPI/GPay via Razorpay)** | Faster collection, fewer cash-handling errors, digital reconciliation. |
| P0 | **User roles & authentication** | Doctors, reception, billing, admin. Required for any multi-user system and for audit. |
| P1 | **Inpatient admission / bed management** | Live bed-occupancy board; admit → transfer → discharge workflow. Core "logistics" ask. |
| P1 | **OT scheduling (2 theatres)** | Books theatre + surgeon + slot; blocks conflicts; surgery list for the day. |
| P1 | **Basic medical record (encounter notes, diagnosis, attachments)** | Lightweight EMR: visit notes, vitals, uploaded reports. *Not* clinical decision support. |
| P1 | **Gujarati/English UI toggle** | Adoption depends on staff comfort. Static i18n. |
| P1 | **Pharmacy integration (read charges → patient bill)** | Pulls dispensed-item charges into the IPD/OPD bill so the final invoice is complete. |
| P2 | **Reports & day-book** | Daily collection report, occupancy, doctor-wise OPD count, GST summary. Operational, not clinical. |
| P2 | **Automated backups & audit log** | Non-negotiable for a production healthcare system (treated as P0 infra, P2 UI). |

### Explicitly OUT of MVP (future phases)

- Clinical decision support, drug-interaction checks, diagnosis suggestions.
- Lab/radiology information system (LIS/RIS) — integrate later; for MVP, attach reports as files.
- Insurance / TPA / cashless claim automation (complex; add when volume justifies).
- Patient mobile app / portal (start with SMS/WhatsApp notifications only).
- Inventory & procurement (pharmacy already has its own software).
- Multi-branch / multi-tenant.
- ABDM / ABHA (Ayushman Bharat Health Account) federation — **design the patient schema to be ABHA-ready** (a nullable `abha_number` field) but defer the full federation flow.
- Advanced analytics / BI dashboards.

### Phasing rationale
- **P0 first** because patient → appointment → bill is the minimum end-to-end revenue loop. A hospital can operate on P0 alone.
- **P1** adds the inpatient/OT logistics that differentiate this from a clinic system.
- **P2** is reporting + hardening, valuable but not blocking go-live.

---

## 2. System Architecture

### 2.1 High-level topology

```
                    ┌─────────────────────────────────────────┐
                    │            Browser (React SPA)           │
                    │   react-i18next · Razorpay Checkout.js   │
                    └───────────────┬──────────────────────────┘
                                    │ HTTPS (JWT in Authorization header)
                    ┌───────────────▼──────────────────────────┐
                    │              Nginx (TLS, reverse proxy)   │
                    └───────────────┬──────────────────────────┘
                                    │
                    ┌───────────────▼──────────────────────────┐
                    │        Flask API (Gunicorn workers)       │
                    │  Blueprints: patients, appts, beds, ot,   │
                    │  billing, payments, users, pharmacy, i18n │
                    │  SQLAlchemy ORM · Marshmallow validation  │
                    │  Flask-JWT-Extended · Alembic migrations  │
                    └──────┬───────────────┬────────────┬───────┘
                           │               │            │
              ┌────────────▼───┐   ┌───────▼─────┐  ┌───▼─────────────┐
              │  PostgreSQL    │   │   Redis     │  │  Pharmacy       │
              │  (primary DB)  │   │ (cache,     │  │  Adapter        │
              │                │   │  rate-limit,│  │ (REST/DB/CSV)   │
              │                │   │  job queue) │  └───┬─────────────┘
              └────────┬───────┘   └─────────────┘      │
                       │                          ┌─────▼──────────────┐
              ┌────────▼────────┐                 │ Standalone Pharmacy │
              │ Nightly backup  │                 │ Software (existing) │
              │ → object store  │                 └─────────────────────┘
              └─────────────────┘

        External: Razorpay (payments) · MSG91/Gupshup (SMS/WhatsApp OTP & alerts)
```

### 2.2 Backend — Flask, and why it fits

**Recommendation: Flask + SQLAlchemy + Marshmallow + Flask-JWT-Extended + Alembic + Gunicorn.**

Rationale for a small-hospital context:
- **Right-sized.** The domain is moderate (10–15 entities, dozens of endpoints), not a microservice estate. Flask's "bring only what you need" model avoids the ceremony of a heavier framework while staying explicit and easy for one maintainer to reason about.
- **Mature ecosystem for exactly these needs:** SQLAlchemy (robust ORM + transactions for billing integrity), Alembic (versioned schema migrations — essential for a system that will evolve), Marshmallow (request/response validation), Flask-JWT-Extended (auth).
- **Operational simplicity.** A single Gunicorn process group behind Nginx is trivial to run on one VM. No Kubernetes, no service mesh — appropriate for "minimal IT support."
- **Hireability.** Python/Flask developers are abundant and affordable in India; future maintenance is easy to staff.

**Concrete library set:**
```
Flask, Flask-SQLAlchemy, Flask-Migrate (Alembic), Flask-JWT-Extended,
marshmallow / flask-marshmallow, Flask-Limiter (rate limiting),
Flask-Cors, psycopg2-binary, gunicorn, python-dotenv,
razorpay (official SDK), redis, celery (or RQ) for async jobs,
structlog (structured logging), pytest (tests).
```

**Project layout (application-factory pattern):**
```
backend/
  app/
    __init__.py          # create_app(), extension init
    config.py            # env-based config (dev/staging/prod)
    extensions.py        # db, jwt, ma, limiter, migrate singletons
    models/              # SQLAlchemy models, one file per aggregate
    schemas/             # Marshmallow schemas (validation + serialization)
    api/                 # Blueprints: patients, appointments, beds, ot,
                         #   billing, payments, users, pharmacy, reports
    services/            # business logic (billing engine, scheduler rules)
    integrations/        # razorpay_client.py, pharmacy_adapter.py, sms.py
    utils/               # errors, audit, pagination, decorators (@roles_required)
  migrations/            # Alembic
  tests/
  wsgi.py
  requirements.txt
  .env.example
```

### 2.3 Database design (PostgreSQL)

**Why PostgreSQL over MySQL/SQLite:** strong transactional integrity (critical for billing), rich constraint support (exclusion constraints prevent double-booking — see below), JSONB for flexible medical-note fields, excellent backup tooling (`pg_dump`, PITR via WAL), and a clear managed path (AWS RDS / DigitalOcean Managed PG) when the hospital outgrows a single VM.

#### Core schema (abbreviated DDL — illustrative)

```sql
-- ============ IDENTITY & ACCESS ============
CREATE TABLE users (
    id            BIGSERIAL PRIMARY KEY,
    full_name     TEXT NOT NULL,
    email         TEXT UNIQUE,
    phone         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,           -- argon2/bcrypt
    role          TEXT NOT NULL CHECK (role IN
                   ('admin','doctor','reception','billing','nurse')),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    locale        TEXT NOT NULL DEFAULT 'en',  -- 'en' | 'gu'
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE doctors (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT REFERENCES users(id),
    specialty     TEXT NOT NULL,           -- 'orthopedics' | 'obgyn'
    reg_number    TEXT,                     -- Medical council reg.
    consult_fee   NUMERIC(10,2) NOT NULL DEFAULT 0
);

-- ============ PATIENT MASTER ============
CREATE TABLE patients (
    id            BIGSERIAL PRIMARY KEY,
    uhid          TEXT UNIQUE NOT NULL,     -- e.g. 'HMS-2026-000123'
    first_name    TEXT NOT NULL,
    last_name     TEXT,
    dob           DATE,
    gender        TEXT CHECK (gender IN ('M','F','O')),
    phone         TEXT NOT NULL,
    alt_phone     TEXT,
    address       TEXT,
    blood_group   TEXT,
    abha_number   TEXT,                     -- nullable; ABDM-ready
    emergency_contact JSONB,
    allergies     TEXT,                      -- free text, surfaced on encounter
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by    BIGINT REFERENCES users(id)
);
CREATE INDEX idx_patients_phone ON patients(phone);
CREATE INDEX idx_patients_name  ON patients(lower(first_name), lower(last_name));

-- ============ APPOINTMENTS (OPD) ============
CREATE TABLE appointments (
    id            BIGSERIAL PRIMARY KEY,
    patient_id    BIGINT NOT NULL REFERENCES patients(id),
    doctor_id     BIGINT NOT NULL REFERENCES doctors(id),
    scheduled_at  TIMESTAMPTZ NOT NULL,
    duration_min  INT NOT NULL DEFAULT 15,
    status        TEXT NOT NULL DEFAULT 'booked'
                   CHECK (status IN ('booked','checked_in','in_progress',
                          'completed','cancelled','no_show')),
    reason        TEXT,
    created_by    BIGINT REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Prevent two appointments for the same doctor in overlapping slots:
ALTER TABLE appointments
  ADD CONSTRAINT no_doctor_overlap
  EXCLUDE USING gist (
     doctor_id WITH =,
     tstzrange(scheduled_at, scheduled_at + (duration_min || ' minutes')::interval)
       WITH &&
  ) WHERE (status NOT IN ('cancelled','no_show'));

-- ============ INPATIENT: WARDS, BEDS, ADMISSIONS ============
CREATE TABLE wards (
    id    BIGSERIAL PRIMARY KEY,
    name  TEXT NOT NULL,
    ward_type TEXT          -- 'general','semi_private','private','icu','maternity'
);
CREATE TABLE beds (
    id        BIGSERIAL PRIMARY KEY,
    ward_id   BIGINT NOT NULL REFERENCES wards(id),
    bed_label TEXT NOT NULL,             -- 'G-12'
    daily_charge NUMERIC(10,2) NOT NULL DEFAULT 0,
    status    TEXT NOT NULL DEFAULT 'available'
               CHECK (status IN ('available','occupied','reserved','maintenance')),
    UNIQUE (ward_id, bed_label)
);
CREATE TABLE admissions (
    id            BIGSERIAL PRIMARY KEY,
    patient_id    BIGINT NOT NULL REFERENCES patients(id),
    attending_doctor_id BIGINT REFERENCES doctors(id),
    bed_id        BIGINT REFERENCES beds(id),
    admitted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    discharged_at TIMESTAMPTZ,
    status        TEXT NOT NULL DEFAULT 'admitted'
                   CHECK (status IN ('admitted','discharged','transferred')),
    diagnosis     TEXT,
    discharge_summary TEXT
);
-- One active admission per bed:
CREATE UNIQUE INDEX one_active_admission_per_bed
  ON admissions(bed_id) WHERE (status = 'admitted');

CREATE TABLE bed_transfers (           -- audit trail of bed moves
    id BIGSERIAL PRIMARY KEY,
    admission_id BIGINT REFERENCES admissions(id),
    from_bed_id  BIGINT REFERENCES beds(id),
    to_bed_id    BIGINT REFERENCES beds(id),
    moved_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    moved_by     BIGINT REFERENCES users(id)
);

-- ============ OPERATION THEATRE SCHEDULING ============
CREATE TABLE operation_theatres (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL                    -- 'OT-1','OT-2'
);
CREATE TABLE ot_bookings (
    id            BIGSERIAL PRIMARY KEY,
    ot_id         BIGINT NOT NULL REFERENCES operation_theatres(id),
    patient_id    BIGINT NOT NULL REFERENCES patients(id),
    surgeon_id    BIGINT NOT NULL REFERENCES doctors(id),
    procedure_name TEXT NOT NULL,
    start_at      TIMESTAMPTZ NOT NULL,
    end_at        TIMESTAMPTZ NOT NULL,
    status        TEXT NOT NULL DEFAULT 'scheduled'
                   CHECK (status IN ('scheduled','in_progress','completed','cancelled')),
    notes         TEXT,
    created_by    BIGINT REFERENCES users(id),
    CHECK (end_at > start_at)
);
-- No double-booking of a theatre, and no surgeon in two OTs at once:
ALTER TABLE ot_bookings ADD CONSTRAINT no_ot_overlap
  EXCLUDE USING gist (ot_id WITH =, tstzrange(start_at, end_at) WITH &&)
  WHERE (status <> 'cancelled');
ALTER TABLE ot_bookings ADD CONSTRAINT no_surgeon_overlap
  EXCLUDE USING gist (surgeon_id WITH =, tstzrange(start_at, end_at) WITH &&)
  WHERE (status <> 'cancelled');

-- ============ MEDICAL RECORD (lightweight) ============
CREATE TABLE encounters (
    id            BIGSERIAL PRIMARY KEY,
    patient_id    BIGINT NOT NULL REFERENCES patients(id),
    doctor_id     BIGINT REFERENCES doctors(id),
    appointment_id BIGINT REFERENCES appointments(id),
    admission_id  BIGINT REFERENCES admissions(id),
    encounter_type TEXT NOT NULL CHECK (encounter_type IN ('opd','ipd','ot')),
    vitals        JSONB,                  -- {bp, pulse, temp, spo2, weight}
    complaints    TEXT,
    diagnosis     TEXT,
    notes         TEXT,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE attachments (
    id BIGSERIAL PRIMARY KEY,
    patient_id BIGINT REFERENCES patients(id),
    encounter_id BIGINT REFERENCES encounters(id),
    file_url   TEXT NOT NULL,             -- object store key, not public
    file_type  TEXT,                       -- 'pdf','image'
    label      TEXT,
    uploaded_by BIGINT REFERENCES users(id),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ BILLING ============
CREATE TABLE service_catalog (             -- master price list
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT,                          -- 'consultation','procedure','bed','lab','other'
    unit_price NUMERIC(10,2) NOT NULL,
    gst_rate NUMERIC(5,2) NOT NULL DEFAULT 0,  -- healthcare often exempt; keep configurable
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE invoices (
    id            BIGSERIAL PRIMARY KEY,
    invoice_no    TEXT UNIQUE NOT NULL,    -- 'INV-2026-000456' (gapless series)
    patient_id    BIGINT NOT NULL REFERENCES patients(id),
    admission_id  BIGINT REFERENCES admissions(id),    -- nullable for OPD
    status        TEXT NOT NULL DEFAULT 'draft'
                   CHECK (status IN ('draft','finalized','partially_paid','paid','cancelled','refunded')),
    subtotal      NUMERIC(12,2) NOT NULL DEFAULT 0,
    tax_total     NUMERIC(12,2) NOT NULL DEFAULT 0,
    discount      NUMERIC(12,2) NOT NULL DEFAULT 0,
    grand_total   NUMERIC(12,2) NOT NULL DEFAULT 0,
    amount_paid   NUMERIC(12,2) NOT NULL DEFAULT 0,
    created_by    BIGINT REFERENCES users(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalized_at  TIMESTAMPTZ
);
CREATE TABLE invoice_line_items (
    id          BIGSERIAL PRIMARY KEY,
    invoice_id  BIGINT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    service_id  BIGINT REFERENCES service_catalog(id),
    description TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'manual'
                 CHECK (source IN ('manual','bed','consultation','ot','pharmacy','lab')),
    source_ref  TEXT,                       -- e.g. pharmacy bill id (idempotency)
    quantity    NUMERIC(10,2) NOT NULL DEFAULT 1,
    unit_price  NUMERIC(10,2) NOT NULL,
    gst_rate    NUMERIC(5,2) NOT NULL DEFAULT 0,
    line_total  NUMERIC(12,2) NOT NULL
);
CREATE TABLE payments (
    id            BIGSERIAL PRIMARY KEY,
    invoice_id    BIGINT NOT NULL REFERENCES invoices(id),
    amount        NUMERIC(12,2) NOT NULL,
    method        TEXT NOT NULL CHECK (method IN ('cash','card','upi','netbanking','razorpay')),
    razorpay_payment_id TEXT,
    razorpay_order_id   TEXT,
    status        TEXT NOT NULL DEFAULT 'captured'
                   CHECK (status IN ('created','captured','failed','refunded')),
    received_by   BIGINT REFERENCES users(id),
    received_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ AUDIT LOG (append-only) ============
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    actor_user_id BIGINT REFERENCES users(id),
    action     TEXT NOT NULL,              -- 'create','update','delete','view_phi','login'
    entity     TEXT NOT NULL,              -- table name
    entity_id  TEXT,
    detail     JSONB,
    ip_address INET,
    at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Key schema decisions:**
- **Postgres exclusion constraints** (`EXCLUDE USING gist` with `tstzrange`) make double-booking *structurally impossible* at the database layer — far safer than application-only checks under concurrent reception staff. (Requires the `btree_gist` extension.)
- **Money is `NUMERIC`**, never float.
- **`source` + `source_ref` on line items** gives idempotent pharmacy/lab imports (re-importing the same pharmacy bill won't duplicate charges).
- **Gapless invoice numbering** via a dedicated sequence table or `SELECT ... FOR UPDATE` counter — required for GST/audit; never rely on `BIGSERIAL` gaps.
- **`audit_log` is append-only** — no UPDATE/DELETE grants for the app role.

### 2.4 Pharmacy integration approach

The pharmacy software is a **black box you don't control**, so use an **Adapter / Anti-Corruption Layer** (`integrations/pharmacy_adapter.py`) that hides *how* you talk to it behind a stable internal interface:

```python
class PharmacyAdapter(Protocol):
    def fetch_charges(self, uhid: str, since: datetime) -> list[PharmacyCharge]: ...
    def health_check(self) -> bool: ...
```

Implement whichever transport the vendor actually supports, in this order of preference:
1. **REST/JSON API** (best): poll `GET /charges?patient=UHID` or receive a webhook. Map to `invoice_line_items` with `source='pharmacy'`, `source_ref=<pharmacy_bill_id>`.
2. **Shared read-only DB view** (common with older Indian pharmacy software like Marg/Vyapar-style tools): grant a read-only SQL user, read a dispensing view. Never write to their DB.
3. **File drop (CSV/Excel)** as fallback: pharmacy exports an end-of-day file to a watched folder/SFTP; a Celery job ingests it.
4. **Manual entry** as the ultimate fallback so the hospital is never blocked.

**Integration contract to demand from the pharmacy vendor** (put this in writing): patient identifier mapping (do they store your UHID? if not, map on phone+name), item description, quantity, amount, GST, a stable bill ID, and timestamp. *This is the single biggest integration risk — confirm the vendor's API/export capability before committing to a transport.*

### 2.5 Deployment strategy for India

- **Primary recommendation: a single managed VM in an India region** (AWS Mumbai `ap-south-1`, or DigitalOcean/Linode Bengaluru) — **data residency in India** matters for DPDP-Act comfort and latency.
- **Managed PostgreSQL** (RDS / DigitalOcean Managed DB) rather than self-hosted DB — automated backups, patching, and point-in-time recovery without IT staff.
- **Reliable internet is stated**, but add a **4G/5G failover router** at the hospital; the system is cloud-hosted so staff need connectivity. Optionally cache the OT/bed board read-only via service worker for brief outages.
- Containerize with **Docker Compose** (api + nginx + redis) for reproducible deploys; keep DB managed/external. Avoid Kubernetes — overkill here.
- See §6 for full infra detail.

---

## 3. Core Module Specifications

Each module below lists: purpose, key endpoints, validation rules, and error handling. All endpoints are JSON, JWT-protected (except auth), role-gated via a `@roles_required(...)` decorator, rate-limited (Flask-Limiter), and return a **consistent error envelope**:

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Phone is required",
             "fields": { "phone": "required" } } }
```
HTTP codes: 400 validation, 401 unauthenticated, 403 wrong role, 404 not found, 409 conflict (e.g. double-booking / bed occupied), 422 business-rule, 500 unexpected (logged with a trace id, never leak internals).

### 3.1 Patient Management

**Purpose:** single source of truth for patient identity and history; admission→discharge lifecycle.

| Endpoint | Role | Notes |
|---|---|---|
| `POST /api/patients` | reception, admin | Register; auto-generate UHID; **duplicate check** on (phone) + fuzzy name match → warn, allow override. |
| `GET /api/patients?q=` | all clinical | Search by UHID/phone/name; paginated. |
| `GET /api/patients/{id}` | all clinical | Full profile + recent encounters. Logged as `view_phi`. |
| `PUT /api/patients/{id}` | reception, admin | Edit demographics. |
| `POST /api/admissions` | reception, doctor | Admit: assigns bed (must be `available`), sets bed `occupied` atomically in one transaction. |
| `POST /api/admissions/{id}/transfer` | nurse, reception | Move bed; writes `bed_transfers`; frees old bed, occupies new. |
| `POST /api/admissions/{id}/discharge` | doctor, admin | Requires discharge summary; frees bed; **triggers final-bill assembly** (pulls bed-days + pharmacy + OT + consults into a finalized invoice). |

**Validation:** phone format (Indian 10-digit), DOB not in future, gender enum, mandatory first name. **Concurrency:** admission + bed status update wrapped in a single DB transaction with `SELECT ... FOR UPDATE` on the bed row to avoid two patients grabbing the same bed.

### 3.2 Appointment / Scheduling System

**Purpose:** OPD booking for 2 doctors, OT scheduling for 2 theatres, live bed availability — all conflict-free.

**OPD appointments:**
- `POST /api/appointments` — body: patient, doctor, slot, duration. Server validates against doctor working hours and the `no_doctor_overlap` exclusion constraint → returns **409** with the conflicting slot if taken.
- `GET /api/appointments?doctor_id=&date=` — day view (calendar grid in UI).
- `PATCH /api/appointments/{id}/status` — check-in / start / complete / no-show / cancel.
- Optional: send SMS/WhatsApp reminder (Celery job, MSG91/Gupshup) the evening before.

**OT scheduling:**
- `POST /api/ot-bookings` — validates theatre free AND surgeon free (two exclusion constraints) → 409 on conflict. Returns the day's OT list per theatre.
- "Surgery list" view: per-OT timeline for the day; status transitions scheduled→in_progress→completed.

**Bed availability board:**
- `GET /api/beds/board` — returns wards → beds with live status and current patient (for occupied). This is the at-a-glance occupancy screen (color-coded). Cache for ~10s in Redis to reduce load.

**Edge cases handled:** overlapping bookings (DB-enforced), cancellation freeing the slot, no-show tracking, double-checked-in prevention. **Time zone:** store UTC (`TIMESTAMPTZ`), render IST (Asia/Kolkata) in the UI.

### 3.3 Billing System

**Purpose:** itemized invoices for OPD & IPD, payment tracking, GST-correct, leakage-proof.

**Invoice lifecycle:** `draft` → (add line items: manual, auto bed-days, consultation fee, OT charge, pharmacy import) → `finalized` (locks, assigns gapless `invoice_no`, computes totals) → `partially_paid`/`paid` as payments post → `cancelled`/`refunded` (with reason + audit).

| Endpoint | Role | Notes |
|---|---|---|
| `POST /api/invoices` | billing, reception | Create draft for patient/admission. |
| `POST /api/invoices/{id}/items` | billing | Add line item; recomputes totals server-side (never trust client totals). |
| `POST /api/invoices/{id}/import-pharmacy` | billing | Idempotent pull via PharmacyAdapter; dedupe on `source_ref`. |
| `POST /api/invoices/{id}/finalize` | billing | Locks invoice, assigns number, validates totals. |
| `GET /api/invoices/{id}/pdf` | billing, reception | Server-rendered PDF (WeasyPrint/ReportLab), bilingual header. |
| `POST /api/payments` | billing, reception | Record cash/card; for online see §3.6. Updates `amount_paid`, recomputes status. |

**Billing rules:**
- All money math **server-side** in `services/billing.py`; line total = `qty × unit_price`, tax per `gst_rate`. Healthcare services are largely **GST-exempt** in India but pharmacy/consumables may not be — keep `gst_rate` per item, default configurable.
- **Bed charges auto-accrue**: a nightly Celery job (or on-discharge calc) adds bed-day line items = `nights × bed.daily_charge`.
- Partial payments allowed; `amount_paid` never exceeds `grand_total` (validation).
- **Gapless invoice numbers** from a locked counter — required for audits.
- Refunds create a negative payment + audit entry; never delete payments.

### 3.4 User Roles & Permissions

| Role | Capabilities |
|---|---|
| **admin** | Everything + user management, service catalog/price edits, reports, audit log view. |
| **doctor** | Own appointments & OT list, patient clinical records, write encounters, discharge. No billing edits, no user mgmt. |
| **reception** | Register patients, book appointments/OT, admit/transfer, create drafts & record payments. No clinical notes edit. |
| **billing** | Full billing/invoices/payments/pharmacy import, financial reports. Read-only clinical. |
| **nurse** | Bed board, transfers, record vitals. (Optional in MVP; can fold into reception.) |

**Implementation:** JWT (short-lived access ~30 min + refresh token), passwords hashed with **Argon2** (or bcrypt), `@roles_required('billing','admin')` decorator on endpoints, account lockout after N failed logins, all auth + PHI-view events written to `audit_log`. Optional **OTP/2FA via SMS** for admin.

### 3.5 Language Toggle (Gujarati / English) — corrected approach

**Do NOT use Google Translate API at runtime.** Use static internationalization:

- **Frontend:** `react-i18next` with two JSON catalogs (`en.json`, `gu.json`) keyed by string id. Toggle in the header flips `i18n.language`; persist choice per user (`users.locale`) and in `localStorage`.
- **Coverage:** all UI chrome, labels, buttons, validation messages, and **PDF invoice headers** localized. Patient names, clinical free-text, and drug names are **never machine-translated** (safety + accuracy).
- **Gujarati strings must be human-reviewed** by a Gujarati-speaking staff member. Google Translate API may be used **once, offline, by the developer** to draft the catalog, but every medical/finance term is verified before shipping. Document this in the README.
- **Fonts:** bundle a Gujarati-capable font (e.g. Noto Sans Gujarati) so rendering is consistent on all machines and in PDFs.
- **Backend:** server-generated messages (errors, SMS, PDFs) also key off a locale param so notifications can be bilingual.

Why this is better: zero per-request cost/latency, no PHI sent to Google, deterministic and safe terminology, works offline. (If the hospital later wants patient-facing free-text translation, that can be a deliberate Phase-3 feature with consent.)

### 3.6 Online Payments (UPI/GPay) — via Razorpay

**Flow (server-authoritative, never trust the client):**
1. Reception/patient chooses "Pay online" on a finalized invoice → `POST /api/payments/order` creates a **Razorpay Order** server-side for the due amount; returns `order_id`.
2. Frontend opens **Razorpay Checkout** (or displays a **UPI QR / payment link** the patient scans in GPay/PhonePe/any UPI app).
3. Patient pays via UPI/GPay/card.
4. **Razorpay webhook** → `POST /api/payments/webhook` (signature-verified with HMAC) is the **source of truth**: on `payment.captured`, insert `payments` row (idempotent on `razorpay_payment_id`), update invoice. Do **not** finalize payment solely on the browser callback.
5. Reconciliation report matches Razorpay settlements to recorded payments.

**Why Razorpay:** single integration exposes UPI (incl. GPay), cards, netbanking, QR, and payment links; strong India support; official Python SDK; handles RBI PA-PG compliance so the hospital doesn't have to. **For pure offline UPI**, also support a **static UPI QR (VPA)** print on the invoice, with manual "mark as paid" + UTR entry as fallback.

**Security:** verify webhook signature, store keys in env/secret manager (never in code), use idempotency keys, log every payment state transition to `audit_log`.

---

## 4. Implementation Roadmap

Complexity: ⚪ low · 🔵 medium · 🔴 high. Sequencing respects dependencies (identity → scheduling/billing → integrations → hardening).

### Phase 0 — Foundations (week 1) — *blocking everything*
- Repo scaffolding (app factory, config, Docker Compose), PostgreSQL + Alembic, CI lint/test. 🔵
- **Auth & users/roles** (JWT, Argon2, `@roles_required`, audit_log skeleton). 🔵
- Error envelope, validation (Marshmallow), structured logging, pagination helper. 🔵
- React app shell, routing, auth guard, **i18n scaffolding (en/gu)**, API client. 🔵

### Phase 1 — Core revenue loop (weeks 2–4) — *P0 features*
- **Patient registration + master index + search** (dedupe). 🔵 *(dep: Phase 0)*
- **OPD appointment scheduling** with exclusion constraints + calendar UI. 🔵 *(dep: patients, doctors)*
- **Billing engine**: catalog, invoices, line items, finalize, PDF. 🔴 *(dep: patients)*
- **Razorpay payments** (order + webhook + reconciliation). 🔴 *(dep: billing)*
- **→ Milestone: hospital can register, book, bill, and collect. Soft-launch OPD.**

### Phase 2 — Inpatient & OT logistics (weeks 5–7) — *P1*
- **Wards/beds + live bed board** with atomic occupancy. 🔵 *(dep: patients)*
- **Admission → transfer → discharge** workflow + auto bed-day billing. 🔴 *(dep: beds, billing)*
- **OT scheduling** (2 theatres, surgeon conflict checks, surgery list). 🔵 *(dep: doctors, patients)*
- **Lightweight encounters/medical record + attachments** (file upload to object store). 🔵 *(dep: patients)*
- **Gujarati catalog complete & reviewed.** ⚪

### Phase 3 — Integration & reporting (weeks 8–9) — *P1/P2*
- **Pharmacy adapter** (confirm vendor transport first!) + idempotent import into bills. 🔴 *(dep: billing; external risk)*
- **SMS/WhatsApp notifications** (appointment reminders, payment receipts). 🔵
- **Reports**: daily collection, occupancy, doctor-wise OPD, GST summary, day-book. 🔵 *(dep: billing, admissions)*

### Phase 4 — Hardening & go-live (week 10) — *production readiness*
- Automated backups + tested **restore drill**, monitoring/alerts, rate limits, security review. 🔵
- Role-based UAT with real staff in both languages; load a real price list; data-entry training. ⚪
- Documentation (admin runbook, user guide, API docs). ⚪

**Total: ~10 weeks for one strong full-stack developer** (or ~6–7 weeks for a 2-person team). Pharmacy integration is the top schedule risk — de-risk it in week 1 by getting the vendor's API/export spec.

---

## 5. Critical Considerations (Healthcare-specific)

### 5.1 Data security & patient privacy (Indian context)
- **Governing law: Digital Personal Data Protection Act, 2023 (DPDP Act)** — health data is sensitive personal data. Also relevant: **IT Act 2000 + SPDI Rules 2011**, **MoHFW EHR Standards 2016**, and **ABDM** guidelines if you later federate via ABHA. (Note: the older *DISHA* bill was never enacted — don't design to it.)
- **Practical controls for the MVP:**
  - **Encryption in transit** (TLS 1.2+ everywhere; HSTS) and **at rest** (managed-DB encryption + encrypted object storage for attachments).
  - **Least privilege:** role-based access; the app DB user has **no DELETE on audit_log**; separate read-only DB user for pharmacy.
  - **Audit trail** of PHI access, edits, logins, payments (already in schema).
  - **Consent & purpose limitation:** capture patient consent at registration; expose patient data only to staff who need it.
  - **Data residency in India** (Mumbai/Bengaluru region).
  - **Secrets** in environment/secret manager, never in the repo; rotate keys.
  - **Backups encrypted**; access to them logged.
  - **PII minimization** in logs (never log full PHI; mask phone/UHID in logs).

### 5.2 Backup & disaster recovery
- **Managed PostgreSQL with automated daily snapshots + Point-In-Time Recovery (WAL)** → target **RPO ≤ 24h (ideally ≤1h with PITR), RTO ≤ 4h**.
- **Nightly logical `pg_dump`** shipped to a **separate region/object store** (defense against region failure and accidental deletion), retained 30 days, **encrypted**.
- **Attachments** in versioned object storage (S3/Spaces) with lifecycle + cross-region replication.
- **Quarterly restore drills** — a backup you've never restored is not a backup. Document the runbook.
- **Failover internet** (4G/5G) at the hospital so cloud access survives ISP outages.

### 5.3 Scalability for future growth
- Stateless Flask behind Gunicorn → scale by adding workers, then a second app instance behind Nginx/load balancer.
- DB: start single managed instance; add **read replica** for reports when needed; indexes already defined on hot paths.
- Redis for caching the bed board and rate limiting; Celery workers scale independently for SMS/imports.
- Schema is **ABDM/ABHA-ready** (`abha_number`) and multi-doctor by design — adding doctors/wards/OTs is data, not code.
- Clean module boundaries (blueprints + services) let you later carve out a service (e.g., billing) if ever needed — but **don't** prematurely microservice.

### 5.4 Pharmacy integration points & API requirements
- **Required from vendor:** stable patient mapping (UHID or phone+name), per-item description/qty/amount/GST, a unique bill id (for idempotency), timestamp, and a transport (REST webhook preferred → read-only DB view → SFTP/CSV → manual).
- **Our side:** Adapter interface (`fetch_charges`, `health_check`), idempotent import keyed on `source_ref`, reconciliation report (pharmacy total vs. imported total), and a **manual fallback** so billing is never blocked by the integration.
- **Failure handling:** if pharmacy is unreachable, mark charges "pending import," alert billing, allow discharge with a flagged provisional bill.

---

## 6. Infrastructure & Deployment

### 6.1 Hosting (recommended baseline)
| Component | Choice | Notes |
|---|---|---|
| Region | AWS `ap-south-1` (Mumbai) or DigitalOcean Bengaluru | Data residency + low latency. |
| App server | 1× VM (2 vCPU / 4 GB to start), Docker Compose: nginx + gunicorn(flask) + redis | Vertical scale first; cheap and simple. |
| Database | **Managed PostgreSQL** (RDS / DO Managed PG), `btree_gist` enabled | Auto backups, PITR, patching. |
| Object storage | S3 / DO Spaces (private, encrypted) | Attachments, PDF archive, backups. |
| TLS | Let's Encrypt via nginx/Certbot (auto-renew) | Free, automated. |
| DNS/CDN | Cloudflare (TLS, basic WAF, DDoS) | Optional but cheap protection. |

### 6.2 Database backup strategy (concrete)
- Managed daily snapshots (retain 7–14 days) **+** WAL PITR.
- Cron `pg_dump` → encrypted → object store in a **different region**, 30-day retention.
- Monthly **restore verification** into a throwaway instance.
- Backup success/failure alerts to admin (email/SMS).

### 6.3 Access patterns for India's connectivity
- Cloud-hosted, browser-accessed over HTTPS from hospital LAN/Wi-Fi; **4G/5G failover** router as backup link.
- Bed/OT boards cached (Redis + short client cache) so brief blips don't disrupt the at-a-glance views; writes require connectivity (acceptable for a hospital with stated reliable internet).
- Lightweight payloads, pagination, and gzip to perform well on variable bandwidth.
- Optional PWA/service-worker read-only caching of today's schedule as a resilience nicety (Phase 3+).

### 6.4 Observability & ops (minimal-IT friendly)
- **Structured logs** (structlog) with request/trace ids; ship to a managed log service or a simple file + logrotate.
- **Uptime/health checks** (`/healthz`) with an external monitor (UptimeRobot) alerting admin.
- **Error tracking** (Sentry free tier) for the Flask app and React.
- **Runbook**: deploy steps, backup/restore, key rotation, "what to do if X is down" — written in plain language for non-IT staff.

---

## 7. Production-Readiness Checklist (build these in, not later)

- [ ] Input validation on every endpoint (Marshmallow), consistent error envelope.
- [ ] Money as NUMERIC; all totals computed server-side.
- [ ] DB-level double-booking prevention (exclusion constraints) + transactional bed/admission updates.
- [ ] Idempotency on payments (webhook) and pharmacy imports.
- [ ] JWT auth, Argon2 hashing, role decorators, rate limiting, account lockout.
- [ ] Append-only audit log of PHI access, edits, payments, logins.
- [ ] TLS everywhere; secrets in env/secret manager; data in India region.
- [ ] Automated encrypted backups **+ tested restore**.
- [ ] i18n catalogs (en/gu), human-reviewed Gujarati, Gujarati-capable fonts in UI + PDFs.
- [ ] Health checks, error tracking, uptime monitoring.
- [ ] README + admin runbook + user guide + API docs (OpenAPI via apispec/flask-smorest).
- [ ] Seed data: doctors, wards/beds, OTs, service catalog/price list.

---

### Appendix A — First things a developer should do (day 1)
1. Scaffold the Flask app-factory + Docker Compose + Postgres + Alembic.
2. Enable `btree_gist`; create the `users`, `patients`, `doctors` migrations.
3. Stand up auth + roles + audit_log.
4. **In parallel: get the pharmacy vendor's integration spec in writing** (the #1 external risk).
5. Build the patient→appointment→invoice→Razorpay vertical slice end-to-end before widening scope.

### Appendix B — Notable libraries
Backend: Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-JWT-Extended, marshmallow, Flask-Limiter, razorpay, celery+redis, WeasyPrint (PDF), structlog, pytest.
Frontend: React, react-router, react-i18next, TanStack Query (data fetching/caching), a calendar component (e.g. FullCalendar) for OPD/OT, Razorpay Checkout.js, a component library (MUI/Chakra) for fast, accessible UI.
