# SurgiCare HMS — Test Plan (50 cases)

Covers everything built so far: Auth/RBAC, Patients, OPD queue + tokens, doctor
coverage, Dashboard, Operation Theatres, i18n, and cross-cutting/extreme cases.

**Tags:** `Happy` normal path · `Edge` boundary · `Negative` invalid input ·
`Security` access/abuse · `Extreme` scale/concurrency/timezone · `i18n` language.

**Preconditions / test data**
- At least 3 app users to fully test RBAC: one `admin`/`reception`, one `doctor`, one `billing`. Set roles via `update public.profiles set role=... where id=...`.
- Migrations 001–006 applied. Doctors: Dr. Mitesh (ortho), Dr. Hetal (obgyn), Dr. Pallavi (obgyn, covers Hetal). Theatres OT-1, OT-2.
- Backend + frontend running; note the date is treated in **IST**.

---

## A. Authentication & Access Control

1. **[Happy] Valid login** — Sign in with a confirmed user → lands on Dashboard; sidebar shows email. *Expected:* session established, `/api/me` returns 200 with role.
2. **[Negative] Wrong password** — Sign in with bad password → red error shows Supabase message ("Invalid login credentials"); no session.
3. **[Edge] Unconfirmed email** — If "Confirm email" is ON, a freshly added user (no Auto-Confirm) → login fails with "Email not confirmed". *Skews dev: silent if you only show a generic message.*
4. **[Security] Protected route while logged out** — Open `/patients` directly without a session → redirected to `/login`.
5. **[Security] Tampered / expired JWT** — Manually corrupt the token in localStorage (or wait for expiry) → `/api/me` returns 401 `UNAUTHENTICATED`; backend log shows `auth.token_invalid`. App should not show stale data.
6. **[Security] Role gating on create** — Log in as a `doctor` role user → `POST /api/patients` (e.g. via the registration form) → **403 FORBIDDEN**. Same as `reception`/`admin` → 201. *Verify the role is read from `profiles`, not the JWT.*
7. **[Security] RLS direct read** — Using the publishable (anon) key directly (e.g. Supabase JS in console) `select * from patients` without a logged-in session → **0 rows / denied** by RLS.
8. **[Edge] Session persistence** — Logged in, hard-refresh the browser → still logged in (no re-login).
9. **[Happy] Logout** — Click Sign out → back to login; protected routes inaccessible until re-login.

## B. Patient Registration & Validation

10. **[Happy] Minimal register** — First name + valid phone → saved; UHID auto-generated as `HMS-2026-000001`; lands on profile.
11. **[Edge] UHID sequence** — Register a 2nd patient → UHID increments (`…000002`), never reused even after deletions.
12. **[Edge] Phone normalization (+91/spaces)** — Enter `+91 98765 43210` → stored as `9876543210`.
13. **[Edge] Phone leading zero** — Enter `098765 43210` (11 digits) → stored as `9876543210`.
14. **[Negative] Phone too short** — `12345` → field error "valid 10-digit Indian mobile".
15. **[Negative] Phone bad prefix** — `5123456789` (starts 1–5) → rejected (regex requires 6–9).
16. **[Negative] Future DOB** — DOB = tomorrow → rejected.
17. **[Edge] DOB = today** — DOB = today's date → **accepted** (boundary).
18. **[Negative] Missing first name** — Blank first name → rejected (required).
19. **[Negative/Security] Oversized name** — First name > 100 chars → validation error (not silently truncated/stored).
20. **[Security] XSS / injection in fields** — First name `<script>alert(1)</script>`; search box `'; DROP TABLE patients;--` → stored/displayed as literal text (React escapes; queries are parameterized). No script runs, no table dropped.
21. **[Happy] Duplicate phone detected** — Register a patient with a phone already on file → 409, yellow warning lists the existing patient(s).
22. **[Edge] Register anyway (force)** — From the duplicate warning, click "Register anyway" → second record created with a **new UHID** but same phone.

## C. Patient Search, Profile & Edit

23. **[Happy] Search by UHID / phone / name** — Each returns the right patient; name search is case-insensitive and matches `first + last`.
24. **[Edge] Empty search** — Clear the box → shows all patients, newest first, paginated (20/page).
25. **[Edge] Pagination boundaries** — With 21+ patients, page 2 loads; **Previous** disabled on page 1, **Next** disabled on last page; counts ("21–25 of 25") correct.
26. **[Edge] Search debounce** — Type quickly then stop → only one request for the final term (no flooding).
27. **[Security] PHI audit on view** — Open a patient profile → an `audit_log` row with action `view_phi`, entity `patients` is written.
28. **[Happy] Edit demographics** — Change address only → saved; `audit_log` `update` row records the changed field(s).
29. **[Negative] Edit to invalid phone** — Edit phone to `000` → rejected with field error; record unchanged.

## D. OPD Sessions (hours)

30. **[Happy] Set & edit hours** — Set OPD hours 10:00–13:00 → shows in gold bar; re-open Edit → prefilled with current values; change & save updates (no duplicate row — one session per doctor/day).
31. **[Negative] Invalid range** — Set end ≤ start (e.g. 13:00–10:00) → rejected (`end_time must be after start_time`).

## E. OPD Queue — Add & Tokens

32. **[Happy] Walk-in → token #1** — Add walk-in (check in) → appears under **Waiting**, token **#1**, `checked_in_at` set.
33. **[Edge] Arrival order** — Add a second walk-in → token **#2** (sequential, per doctor per day).
34. **[Happy] Pre-book → no token** — Pre-book a patient → under **Booked – not arrived**, **no token** (shows "—").
35. **[Edge] Check-in assigns next token** — Check in the pre-booked patient → moves to Waiting, token = **next** (#3); token decided at check-in, not booking.
36. **[Happy] New patient walk-in** — In Add panel, choose **New patient**, enter name + fresh phone, Add walk-in → profile auto-created (visible in Patients) + queued with a token.
37. **[Edge] New patient with existing phone** — New patient with a phone already on file → panel auto-switches to **Returning** with that existing patient selected + info note; **no duplicate** created.
38. **[Negative] Add without patient** — Returning mode, click Add without selecting → "Please select a patient". New mode without name/phone → "Enter at least a first name and phone".

## F. OPD Queue — Status Workflow

39. **[Happy] Full lifecycle** — Booked → Check in → Call in → Complete. Each step moves the card to the right group; `called_at`/`completed_at` timestamps set.
40. **[Happy] No-show & cancel** — From Waiting: No show → Done group; Cancel → removed from the list entirely (excluded from queries).
41. **[Extreme] Token continuity after cancel** — With tokens #1,#2,#3, cancel #2, then add a new walk-in → it gets **#4** (max+1), not a reused #2. *Confirm gaps are acceptable to staff.*
42. **[Edge] Independent doctor sequences** — Same day, Dr. Mitesh's first patient is #1 and Dr. Hetal's first patient is also #1 (tokens are per doctor).
43. **[Edge] New day resets** — Change the date → token numbering starts at #1 again for that date.
44. **[Negative/Behavior] Out-of-order status via API** — `PATCH /api/queue/{id}/status` to `completed` on a still-`booked` entry → **currently allowed** (no strict state machine). *Decide if you want to enforce transitions; today the API trusts the caller.*

## G. Doctor Coverage (one-way)

45. **[Happy] Coverage view** — Queue under **Dr. Hetal** shows only her patients. Switch to **Dr. Pallavi (covers Dr. Hetal)** → shows Pallavi's **and** Hetal's, with a "Dr. Hetal Desai" chip on covered rows.
46. **[Edge] One-way only** — A patient queued under **Pallavi** does **not** appear under **Dr. Hetal**'s view. Same rule on OT via the Surgeon filter.

## H. Dashboard

47. **[Happy] Live totals** — Register a patient and add queue entries → Dashboard "Total patients", "Registered today", "In queue today", "Waiting now", "Seen today" reflect them; per-doctor cards show waiting/in-consult/done and "Now serving #token".
48. **[Extreme] IST date boundary** — A patient created at ~00:05 IST counts under **today** (not yesterday); one created at 23:55 IST yesterday is **not** in "Registered today". *Verify the `AT TIME ZONE 'Asia/Kolkata'` logic; a naive UTC count would misreport near midnight.*

## I. Operation Theatres

49. **[Happy + Edge] OT case list & reorder** — Add 3 cases to OT-1 → numbered #1–#3 in add order. Reorder with ▲/▼ → order swaps; ▲ on the top case and ▼ on the last are no-ops (disabled). Start/Complete/Cancel transition correctly; cancelled cases drop off. OT-2 keeps an independent list. Empty procedure → rejected; surgeon filter for Pallavi shows Hetal's cases too.

## J. Resilience, Concurrency & i18n

50. **[Extreme/i18n] Stress + failure + language** —
    (a) **Scale:** add 50+ patients to one doctor's queue in a day → tokens reach #50+, list and dashboard counts stay correct/performant.
    (b) **Concurrency:** trigger two near-simultaneous walk-in check-ins for the same doctor → the `uq_queue_token` unique index prevents two identical tokens (one errors instead of duplicating). *Confirm no two patients share a token.*
    (c) **Backend down:** stop uvicorn, attempt any action → UI shows the error (not an infinite spinner) and recovers when the backend returns. **DB down:** `/healthz` reports `database: down`; protected endpoints return 503 `DB_UNAVAILABLE` rather than crashing.
    (d) **Language:** toggle EN→ગુ → every label, status, group title, and action translates; choice persists across refresh; Gujarati renders in the proper font (no missing-glyph boxes) on screen.

---

### Notes / known gaps surfaced by this plan
- **Status transitions are not strictly enforced** server-side (case 44) — the UI guides the flow, but the API accepts any valid status. Decide whether to lock this down.
- **Token gaps after cancellation** (case 41) are by design (max+1) — confirm staff are fine with non-contiguous tokens, or switch to renumbering.
- **Billing, beds/wards, medical records** are not built yet — out of scope for this pass.
- For RBAC tests (6, 7) you need users with `doctor`/`billing` roles; the default profile role is `reception`.
