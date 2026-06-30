# HMS MVP — 30-Day Roadmap (one feature at a time, build → test → done)

**Stack (revised):**
- **Database + Auth + Storage:** Supabase (managed Postgres, Supabase Auth/JWT, Supabase Storage, Row-Level Security).
- **Backend API:** **FastAPI** (Python) — single framework. *Not* Flask+FastAPI both; FastAPI only. Pydantic for validation, auto OpenAPI docs.
- **Frontend / UI:** React, **designed with Claude** (generate screens/components via Claude, then wire to the API). Supabase JS client for auth; `react-i18next` for Gujarati/English.
- **Payments:** Razorpay (UPI/GPay). **Reference:** full architecture & schema in `HMS-MVP-Technical-Specification.md`.

**Working method — every feature follows the same loop:**
1. **DB:** migration + RLS policy in Supabase.
2. **API:** FastAPI endpoint(s) + Pydantic schemas + business logic.
3. **UI:** Claude-designed React screen wired to the API (bilingual).
4. **Test:** unit (pytest) + integration (API against a Supabase test project) + manual acceptance checklist.
5. **Done gate:** all tests green, manual checklist passes, demoed. *Only then move to the next feature.*

> Assumption: solo developer, ~6 focused hours/day. A 2-person team compresses this to ~3 weeks. If you instead meant "spend all 30 days perfecting a single feature," tell me which one and I'll expand it.

---

## How Supabase changes the earlier design

| Concern | Earlier (self-hosted) | Now (Supabase) |
|---|---|---|
| Auth | Roll JWT + Argon2 yourself | **Supabase Auth** issues JWTs; FastAPI verifies them; roles via `app_metadata.role` + a `profiles` table |
| Data security | App-level checks | **Row-Level Security (RLS) policies** enforce access at the DB — defense in depth |
| File storage | S3 + signed URLs | **Supabase Storage** buckets (private) + signed URLs |
| Backups | Manual pg_dump | Supabase **daily backups + PITR** (Pro plan); still add an off-platform `pg_dump` |
| Region | Pick a VM region | Choose Supabase **Mumbai (ap-south-1)** for data residency |

**Two access paths from React:** (1) simple authenticated reads go straight to Supabase (RLS-protected); (2) anything with business rules — billing math, scheduling conflicts, payments, pharmacy import — goes through **FastAPI**, which uses the service-role key and writes the audit log. Keep money/scheduling logic in FastAPI, never in the browser.

---

## Week 1 — Foundation + Feature 1: Patient Management

**Days 1–2 · Foundation (prerequisite, not a feature)**
- Create Supabase project (Mumbai region). Enable `btree_gist`. Apply core migrations from the spec (`patients`, `doctors`, `users/profiles`, `audit_log`).
- Write **RLS policies**: authenticated staff can read patients; only `reception`/`admin` can insert/update; `audit_log` is insert-only.
- Scaffold **FastAPI** (app factory, settings, `supabase-py`/asyncpg client, dependency that **verifies Supabase JWT** and extracts role). Add `/healthz`, error envelope, structured logging.
- **Claude-design the UI shell:** prompt Claude for an app layout (sidebar nav, header with language toggle + user menu), a design system (colors, typography incl. Gujarati font), and a reusable form/table kit. Wire Supabase Auth login.
- *Gate:* login works, JWT flows to FastAPI, role is read, blank authenticated dashboard renders in EN + GU.

**Days 3–5 · Feature 1: Patient registration, search, profile**
- API: `POST /patients` (auto UHID, duplicate check on phone + fuzzy name), `GET /patients?q=` (paginated), `GET /patients/{id}`, `PUT /patients/{id}`.
- UI (Claude-designed): registration form with validation, search-as-you-type list, patient profile page.
- **Tests:** pytest for UHID generation + dedupe logic + validation; integration test hitting the test Supabase project; manual checklist (register, find by phone/name, edit, duplicate warning, both languages).

**Days 6–7 · Stabilize Feature 1**
- Edge cases (missing fields, bad phone, duplicate override), `view_phi` audit logging, empty/error states in UI.
- *Done gate:* Feature 1 fully working + tested. **Demo: register and retrieve a patient end-to-end.**

---

## Week 2 — Feature 2: Appointment Scheduling (2 doctors)

**Days 8–10 · Build**
- DB: `appointments` + the `no_doctor_overlap` **exclusion constraint** (double-booking impossible at DB level). RLS for clinical roles.
- API: `POST /appointments` (validates working hours; returns **409** on conflict with the clashing slot), `GET /appointments?doctor_id=&date=`, `PATCH /appointments/{id}/status` (check-in → in_progress → completed → no_show/cancel).
- UI: Claude-designed **day calendar** per doctor (e.g. FullCalendar), booking modal, status chips.

**Days 11–12 · Test**
- pytest for conflict rejection, status transitions, timezone handling (store UTC, show IST).
- Manual: book, prevent overlap, cancel frees slot, no-show, bilingual labels.

**Days 13–14 · Stabilize + optional reminders**
- Optional: SMS/WhatsApp reminder job (MSG91/Gupshup) — can defer to Week 5 buffer.
- *Done gate:* scheduling works, conflicts provably blocked, tests green. **Demo: book two doctors, attempt a clash, see it rejected.**

---

## Week 3 — Feature 3: Billing + Feature 4: Online Payments

**Days 15–18 · Feature 3: Billing engine (the hardest feature — give it room)**
- DB: `service_catalog`, `invoices`, `invoice_line_items`, `payments`. **Gapless invoice number** counter.
- API: create draft → add line items (**totals computed server-side**, NUMERIC money) → finalize (locks, assigns number) → record cash/card payment → invoice **PDF** (WeasyPrint, bilingual header).
- UI: invoice builder (pick services from catalog, qty, discount, live totals), invoice list, PDF download/print.
- **Tests:** pytest for totals, GST, partial payments not exceeding total, gapless numbering under concurrency; manual: build → finalize → pay → print in both languages.

**Days 19–21 · Feature 4: Razorpay (UPI/GPay)**
- API: `POST /payments/order` (server-side Razorpay order), `POST /payments/webhook` (**HMAC-verified, idempotent on `razorpay_payment_id`** — the source of truth), reconciliation read.
- UI: "Pay online" → Razorpay Checkout / UPI QR on the invoice; live status.
- **Tests:** webhook signature verification, idempotent double-webhook, failed-payment path; manual test in Razorpay **test mode**.
- *Done gate:* take a real (test-mode) UPI payment that posts via webhook and updates the invoice. **Demo: invoice → pay by UPI → auto-marked paid.**

---

## Week 4 — Feature 5: Beds/Admissions + Feature 6: OT Scheduling

**Days 22–24 · Feature 5: Inpatient beds & admission lifecycle**
- DB: `wards`, `beds`, `admissions`, `bed_transfers`; unique active-admission-per-bed; RLS.
- API: bed **board** (`GET /beds/board`), admit (atomic bed-occupy in one transaction), transfer, **discharge** (frees bed, auto-adds bed-day charges to the invoice).
- UI: Claude-designed **color-coded bed board**, admit/transfer/discharge flows.
- **Tests:** atomic bed grab (no two patients, same bed), bed-day billing on discharge; manual lifecycle.

**Days 25–27 · Feature 6: OT scheduling (2 theatres)**
- DB: `operation_theatres`, `ot_bookings` + **two exclusion constraints** (theatre free AND surgeon free).
- API: book (409 on theatre/surgeon clash), daily surgery list, status transitions.
- UI: per-OT timeline + booking form.
- **Tests:** conflict rejection for theatre and surgeon; manual surgery-list flow.

**Day 28 · Lightweight medical record (if time)**
- `encounters` (vitals JSONB, complaints, diagnosis, notes) + `attachments` to **Supabase Storage** (private bucket, signed URLs). *Not* clinical decision support. Defer to Phase 2 if tight.
- *Done gate:* admit → assign bed → discharge with auto-billing; book both OTs without clashes. **Demo inpatient + OT flows.**

---

## Days 29–30 — Hardening, Backups & Go-Live

- **Backups/DR:** confirm Supabase PITR; add a **nightly off-platform `pg_dump`** (encrypted, separate storage) and run **one restore drill**.
- **Security pass:** review every RLS policy, verify FastAPI role-gating, secrets in env, TLS, audit log covers PHI views/edits/payments/logins.
- **Bilingual UAT** with real staff; load the real **service price list**, doctors, wards/beds, OTs (seed data).
- **Docs:** README, admin runbook ("what to do if X is down"), short user guide; OpenAPI is auto-generated by FastAPI.
- **Deploy:** FastAPI container on a Mumbai VM (or Fly.io/Render ap-south) behind Nginx+TLS; React on Vercel/Netlify or the same VM; Supabase is already hosted.
- *Final gate:* full path — register → book → admit → bill → UPI pay → discharge → print — passes in EN and GU, with backups verified.

---

## Feature dependency order (why this sequence)
```
Foundation (auth, RLS, schema)
   └─► Patients ─┬─► Appointments
                 ├─► Billing ─► Payments
                 ├─► Beds/Admissions ─► (bed-day) Billing
                 └─► OT Scheduling
```
Patients unblock everything; billing must exist before payments and before bed-day/OT charges can land on an invoice. Each box is a fully tested vertical slice before the next starts.

## Risks to front-load (do in Week 1, in parallel)
- **Pharmacy integration spec** from the existing vendor (API vs DB-view vs CSV). Highest external risk; not on the critical 30-day path but confirm transport now. Pharmacy charge import is a **post-30-day Phase 2** item.
- **Razorpay account + KYC** can take days — start the sign-up on Day 1 so test keys are ready by Week 3.
- **Gujarati translation review** — line up a Gujarati-speaking staff reviewer before Week 4 UAT.

## Per-feature Definition of Done (apply to all six)
- [ ] Migration + RLS policy applied in Supabase
- [ ] FastAPI endpoints with Pydantic validation + consistent error envelope
- [ ] Business logic unit-tested (pytest), happy + edge paths
- [ ] Integration test against test Supabase project passes
- [ ] Claude-designed UI wired, works in English **and** Gujarati
- [ ] Audit log entries written where PHI/money is touched
- [ ] Manual acceptance checklist signed off + demoed
