#!/usr/bin/env python3
"""SurgiCare HMS → Visual Chemist pharmacy bridge.

Runs on the pharmacy's Windows PC. Every few seconds it pulls prescriptions
that doctors have issued (status 'pending') from the HMS API, writes each one
as a CSV + JSON file into a local folder, then tells the HMS it was delivered.
Visual Chemist (or whoever) imports the files from that folder.

Deliberately stdlib-only: no `pip install` needed — just Python 3.8+.

Config comes from a `.env` file next to this script (see .env.example), with
real environment variables taking precedence. Run:

    python bridge.py            # loop forever, polling every POLL_SECONDS
    python bridge.py --once     # single pass then exit (good for a scheduled task)
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


# --------------------------- config ---------------------------
def load_env() -> None:
    """Load KEY=VALUE lines from ./.env into os.environ (without overriding
    values already set in the real environment)."""
    env_path = HERE / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# --------------------------- logging ---------------------------
def log(msg: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    try:
        with open(HERE / "bridge.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass  # logging must never crash the bridge


# --------------------------- HTTP ---------------------------
def api_get(base: str, path: str, token: str) -> dict:
    req = urllib.request.Request(
        base.rstrip("/") + path,
        headers={"X-Bridge-Token": token, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_post(base: str, path: str, token: str) -> None:
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=b"",
        method="POST",
        headers={"X-Bridge-Token": token, "Content-Length": "0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


# --------------------------- file writing ---------------------------
# CSV columns are a sensible default. Once you confirm what Visual Chemist's
# import expects, adjust CSV_COLUMNS / row() below to match — nothing else
# needs to change.
CSV_COLUMNS = [
    "prescription_id", "issued_at", "uhid", "patient_name", "phone",
    "dob", "gender", "doctor", "doctor_specialty",
    "drug_name", "strength", "frequency", "duration", "quantity",
    "instructions", "rx_notes",
]


def rows_for(payload: dict) -> list[dict]:
    patient = payload.get("patient") or {}
    doctor = payload.get("doctor") or {}
    base = {
        "prescription_id": payload.get("prescription_id"),
        "issued_at": payload.get("issued_at"),
        "uhid": patient.get("uhid"),
        "patient_name": patient.get("name"),
        "phone": patient.get("phone"),
        "dob": patient.get("dob"),
        "gender": patient.get("gender"),
        "doctor": doctor.get("name"),
        "doctor_specialty": doctor.get("specialty"),
        "rx_notes": payload.get("notes"),
    }
    items = payload.get("items") or []
    if not items:
        return [dict(base, drug_name="", strength="", frequency="",
                     duration="", quantity="", instructions="")]
    return [
        dict(base,
             drug_name=it.get("drug_name"), strength=it.get("strength"),
             frequency=it.get("frequency"), duration=it.get("duration"),
             quantity=it.get("quantity"), instructions=it.get("instructions"))
        for it in items
    ]


def write_files(out_dir: Path, payload: dict, formats: set[str]) -> None:
    pid = payload.get("prescription_id", "unknown")
    out_dir.mkdir(parents=True, exist_ok=True)
    if "json" in formats:
        tmp = out_dir / f"rx_{pid}.json.tmp"
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(out_dir / f"rx_{pid}.json")
    if "csv" in formats:
        tmp = out_dir / f"rx_{pid}.csv.tmp"
        with open(tmp, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for row in rows_for(payload):
                writer.writerow(row)
        tmp.replace(out_dir / f"rx_{pid}.csv")


# --------------------------- main loop ---------------------------
def process_once(base: str, token: str, out_dir: Path, formats: set[str]) -> int:
    data = api_get(base, "/api/pharmacy/bridge/pending", token)
    items = data.get("items", [])
    if not items:
        return 0
    delivered = 0
    for entry in items:
        outbox_id = entry["id"]
        payload = entry.get("payload") or {}
        pid = payload.get("prescription_id", outbox_id)
        try:
            write_files(out_dir, payload, formats)
        except OSError as exc:
            log(f"ERROR writing files for Rx {pid}: {exc}")
            continue  # leave it pending; retry next cycle
        try:
            api_post(base, f"/api/pharmacy/bridge/sent/{outbox_id}", token)
        except urllib.error.URLError as exc:
            log(f"WARN wrote Rx {pid} but could not mark sent ({exc}); will retry")
            continue
        delivered += 1
        log(f"Delivered Rx {pid} (outbox #{outbox_id}) → {out_dir}")
    return delivered


def main() -> int:
    load_env()
    base = cfg("HMS_API_URL")
    token = cfg("PHARMACY_BRIDGE_TOKEN")
    out_dir = Path(cfg("OUTPUT_DIR", str(HERE / "outbox")))
    formats = {f.strip().lower() for f in cfg("FILE_FORMATS", "csv,json").split(",") if f.strip()}
    poll = int(cfg("POLL_SECONDS", "15") or "15")
    once = "--once" in sys.argv

    if not base or not token:
        log("FATAL: set HMS_API_URL and PHARMACY_BRIDGE_TOKEN in .env")
        return 2

    log(f"Bridge starting — polling {base} every {poll}s, writing {sorted(formats)} to {out_dir}")
    while True:
        try:
            n = process_once(base, token, out_dir, formats)
            if n:
                log(f"Cycle done — {n} prescription(s) delivered")
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                log("FATAL: 401 Unauthorized — PHARMACY_BRIDGE_TOKEN does not match the server")
                return 3
            log(f"HTTP error {exc.code}: {exc.reason}")
        except urllib.error.URLError as exc:
            log(f"Cannot reach HMS API ({exc.reason}) — will retry")
        except Exception as exc:  # noqa: BLE001 - a bridge must keep running
            log(f"Unexpected error: {exc}")
        if once:
            return 0
        time.sleep(poll)


if __name__ == "__main__":
    raise SystemExit(main())
