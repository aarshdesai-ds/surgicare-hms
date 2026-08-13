# SurgiCare pharmacy bridge

A tiny agent that runs on the **pharmacy's Windows PC** and delivers doctors'
prescriptions from the HMS into a folder that Visual Chemist can import.

It **pulls** from the HMS API (the pharmacy PC is never contacted directly), so
it works even though the pharmacy machine isn't reachable from the server. The
only requirement is that the pharmacy PC has **outbound** network access to the
HMS backend URL.

```
Doctor prescribes  →  HMS pharmacy_outbox (pending)
                              │  (bridge polls every ~15s over HTTPS)
                              ▼
                    bridge.py on pharmacy PC
                              │  writes rx_<id>.csv + rx_<id>.json
                              ▼
                    C:\SurgiCare\pharmacy-inbox\   →  Visual Chemist import
                              │
                              ▼
                    HMS marks the prescription "sent"
```

## Why files (for now)

Visual Chemist is an offline Windows app with no confirmed API. Dropping
standard files into a folder is the safe, vendor-neutral path: it can't corrupt
VC's data, and the moment you confirm what VC's import wants, only the CSV
columns need adjusting — see **Matching Visual Chemist's format** below.

## Setup (pharmacy PC)

1. Install **Python 3.8+** from python.org (tick *Add Python to PATH*). No other
   packages are needed — the bridge uses only the standard library.
2. Copy this whole `pharmacy-bridge` folder onto the pharmacy PC.
3. Copy `.env.example` to `.env` and fill it in:
   - `HMS_API_URL` — where the pharmacy PC can reach the backend (LAN IP like
     `http://192.168.1.50:8000`, or your deployed URL).
   - `PHARMACY_BRIDGE_TOKEN` — must match the backend's `.env`. Generate one on
     the server with:
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(32))"
     ```
     Put the same value in the backend `.env` (`PHARMACY_BRIDGE_TOKEN=...`) and
     here, then restart the backend.
   - `OUTPUT_DIR` — the folder VC imports from (e.g. `C:\SurgiCare\pharmacy-inbox`).
4. Test it once:
   ```bat
   python bridge.py --once
   ```
   Issue a prescription in the HMS, run that, and check `OUTPUT_DIR` for
   `rx_<id>.csv` / `rx_<id>.json`.
5. Run it continuously: double-click `run-bridge.bat`, or register it as a
   **Scheduled Task** (trigger *At log on*, action *Start `run-bridge.bat`*) so
   it survives reboots.

## What each prescription produces

- `rx_<id>.json` — the full prescription payload (patient, doctor, drug lines).
- `rx_<id>.csv` — one row **per drug line** with these columns:
  `prescription_id, issued_at, uhid, patient_name, phone, dob, gender, doctor,
  doctor_specialty, drug_name, strength, frequency, duration, quantity,
  instructions, rx_notes`

Files are written atomically (`.tmp` then rename) so VC never sees a half-written
file, and a prescription is marked **sent** in the HMS only after its files are
written.

## Matching Visual Chemist's format

The CSV above is a reasonable default, not VC's spec. Ask your Visual Chemist
vendor:

1. Can VC **import** a prescription/sale from a file? Which format — CSV, Excel,
   XML, or a fixed layout?
2. If CSV/Excel: what **exact column names/order** does it expect, and does it
   key medicines by name or by an internal item code?
3. Can it **watch a folder** and auto-import, or must someone click Import?
4. If not files — does it expose a database (it reportedly supports PostgreSQL)
   or any API we could target instead?

With answers to 1–2, editing `CSV_COLUMNS` and `rows_for()` in `bridge.py` is a
5-minute change. Answers to 4 would let us switch to a direct DB/API adapter for
a fully hands-off flow.

## Security

- The token only unlocks the two pharmacy-outbox endpoints — it can't read
  patients, billing, or anything else. Rotate it any time by changing both
  `.env` files and restarting the backend.
- `.env`, `outbox/`, and `bridge.log` are git-ignored — never commit them.
