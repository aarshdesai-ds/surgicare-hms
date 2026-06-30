"""Integration tests against a real Postgres (skipped unless TEST_DATABASE_URL).

Each test runs in a rolled-back transaction (see conftest `conn`), so nothing
persists. These cover the DB-driven behaviours that unit tests can't: UHID
generation, duplicate detection, token sequencing, doctor coverage, encounters,
and OT case ordering. They call the service layer directly with the test
connection.
"""

from __future__ import annotations

import pytest

from app.errors import AppError
from app.schemas.encounter import EncounterCreate
from app.schemas.ot import OTCaseCreate, OTMove
from app.schemas.patient import PatientCreate
from app.schemas.queue import QueueAdd, QueueStatusUpdate
from app.services import encounters as enc_svc
from app.services import ot as ot_svc
from app.services import patients as patients_svc
from app.services import queue as queue_svc

from .conftest import TEST_DATE

# All tests here need the `conn` fixture, which skips without TEST_DATABASE_URL.
pytestmark = pytest.mark.usefixtures("conn")


async def _first_doctor(conn) -> int:
    did = await conn.fetchval("SELECT id FROM public.doctors ORDER BY id LIMIT 1")
    if not did:
        pytest.skip("no doctors seeded in the test database")
    return did


# --- Patients: UHID + duplicate detection (cases 10, 11, 21, 22) -------------
async def test_uhid_generated_and_dedupe(conn):
    p = await patients_svc.create(
        conn, PatientCreate(first_name="Test", phone="9000000001"), actor_id=None
    )
    assert p["uhid"].startswith("HMS-")

    with pytest.raises(AppError) as exc:
        await patients_svc.create(
            conn, PatientCreate(first_name="Dup", phone="9000000001"), actor_id=None
        )
    assert exc.value.status_code == 409
    assert exc.value.code == "DUPLICATE_PATIENT"

    # force overrides the duplicate guard -> a second distinct record
    p2 = await patients_svc.create(
        conn, PatientCreate(first_name="Dup", phone="9000000001"),
        actor_id=None, force=True,
    )
    assert p2["id"] != p["id"]
    assert p2["uhid"] != p["uhid"]


# --- Queue: token sequencing + check-in (cases 32-35, 41) --------------------
async def test_token_sequencing_and_checkin(conn):
    did = await _first_doctor(conn)
    a = await patients_svc.create(conn, PatientCreate(first_name="A", phone="9000000002"), None)
    b = await patients_svc.create(conn, PatientCreate(first_name="B", phone="9000000003"), None)
    c = await patients_svc.create(conn, PatientCreate(first_name="C", phone="9000000004"), None)

    e1 = await queue_svc.add(conn, QueueAdd(doctor_id=did, patient_id=a["id"], queue_date=TEST_DATE, check_in=True), None)
    e2 = await queue_svc.add(conn, QueueAdd(doctor_id=did, patient_id=b["id"], queue_date=TEST_DATE, check_in=True), None)
    assert e1["token_no"] == 1
    assert e2["token_no"] == 2
    assert e1["status"] == "waiting"

    # pre-book -> no token
    e3 = await queue_svc.add(conn, QueueAdd(doctor_id=did, patient_id=c["id"], queue_date=TEST_DATE, check_in=False), None)
    assert e3["token_no"] is None
    assert e3["status"] == "booked"

    # check in -> assigned the next token
    e3b = await queue_svc.update_status(conn, e3["id"], QueueStatusUpdate(status="waiting"), None)
    assert e3b["token_no"] == 3


async def test_token_gap_after_cancel(conn):
    did = await _first_doctor(conn)
    a = await patients_svc.create(conn, PatientCreate(first_name="A", phone="9000000005"), None)
    b = await patients_svc.create(conn, PatientCreate(first_name="B", phone="9000000006"), None)
    e1 = await queue_svc.add(conn, QueueAdd(doctor_id=did, patient_id=a["id"], queue_date=TEST_DATE, check_in=True), None)
    await queue_svc.update_status(conn, e1["id"], QueueStatusUpdate(status="cancelled"), None)
    e2 = await queue_svc.add(conn, QueueAdd(doctor_id=did, patient_id=b["id"], queue_date=TEST_DATE, check_in=True), None)
    # token continues past the cancelled one (max+1), not reused
    assert e2["token_no"] == 2


# --- Doctor coverage, one-way (cases 45, 46) ---------------------------------
async def test_coverage_one_way(conn):
    hetal = await conn.fetchval(
        "SELECT id FROM public.doctors WHERE full_name = 'Dr. Hetal Desai'"
    )
    pallavi = await conn.fetchval(
        "SELECT id FROM public.doctors WHERE full_name = 'Dr. Pallavi N. Patel'"
    )
    if not hetal or not pallavi:
        pytest.skip("expected doctor names not present")
    cov = await conn.fetchval(
        "SELECT covers_for_doctor_id FROM public.doctors WHERE id = $1", pallavi
    )
    if cov != hetal:
        pytest.skip("coverage link not configured (run migration 006)")

    ph = await patients_svc.create(conn, PatientCreate(first_name="H", phone="9000000010"), None)
    pp = await patients_svc.create(conn, PatientCreate(first_name="P", phone="9000000011"), None)
    await queue_svc.add(conn, QueueAdd(doctor_id=hetal, patient_id=ph["id"], queue_date=TEST_DATE, check_in=True), None)
    await queue_svc.add(conn, QueueAdd(doctor_id=pallavi, patient_id=pp["id"], queue_date=TEST_DATE, check_in=True), None)

    hetal_pids = {x["patient_id"] for x in await queue_svc.list_queue(conn, TEST_DATE, hetal)}
    pallavi_pids = {x["patient_id"] for x in await queue_svc.list_queue(conn, TEST_DATE, pallavi)}

    # Hetal sees only her own
    assert ph["id"] in hetal_pids
    assert pp["id"] not in hetal_pids
    # Pallavi (covering) sees both
    assert ph["id"] in pallavi_pids
    assert pp["id"] in pallavi_pids


# --- Encounters (consultation notes) -----------------------------------------
async def test_encounter_create_and_list(conn):
    p = await patients_svc.create(conn, PatientCreate(first_name="E", phone="9000000020"), None)
    e = await enc_svc.create(
        conn,
        EncounterCreate(patient_id=p["id"], diagnosis="Test dx", vitals={"bp": "120/80"}),
        actor_id=None,
    )
    assert e["diagnosis"] == "Test dx"
    lst = await enc_svc.list_for_patient(conn, p["id"])
    assert len(lst) == 1
    assert lst[0]["vitals"]["bp"] == "120/80"


# --- OT case ordering + reorder (case 49) ------------------------------------
async def test_ot_positions_and_reorder(conn):
    did = await _first_doctor(conn)
    tid = await conn.fetchval(
        "SELECT id FROM public.operation_theatres ORDER BY id LIMIT 1"
    )
    if not tid:
        pytest.skip("no theatres seeded")
    pa = await patients_svc.create(conn, PatientCreate(first_name="S1", phone="9000000030"), None)
    pb = await patients_svc.create(conn, PatientCreate(first_name="S2", phone="9000000031"), None)

    c1 = await ot_svc.add(conn, OTCaseCreate(theatre_id=tid, case_date=TEST_DATE, patient_id=pa["id"], surgeon_id=did, procedure="P1"), None)
    c2 = await ot_svc.add(conn, OTCaseCreate(theatre_id=tid, case_date=TEST_DATE, patient_id=pb["id"], surgeon_id=did, procedure="P2"), None)
    assert c1["position"] == 1
    assert c2["position"] == 2

    moved = await ot_svc.move(conn, c2["id"], OTMove(direction="up"), None)
    assert moved["position"] == 1
