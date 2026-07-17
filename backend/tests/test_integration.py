"""Integration tests against a real Postgres (skipped unless TEST_DATABASE_URL).

Each test runs in a rolled-back transaction (see conftest `conn`), so nothing
persists. These cover the DB-driven behaviours that unit tests can't: UHID
generation, duplicate detection, token sequencing, doctor coverage, encounters,
and OT case ordering. They call the service layer directly with the test
connection.
"""

from __future__ import annotations

import pytest

from decimal import Decimal

from app.errors import AppError
from app.schemas.billing import (
    InvoiceCreate, LineItemCreate, PaymentCreate,
)
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


async def test_labor_room_is_obgyn_only(conn):
    labor = await conn.fetchrow(
        "SELECT id FROM public.operation_theatres WHERE obgyn_only = true LIMIT 1"
    )
    if labor is None:
        pytest.skip("no OB-GYN-only theatre (run migration 009)")
    ortho = await conn.fetchval(
        "SELECT id FROM public.doctors WHERE specialty = 'orthopedics' LIMIT 1"
    )
    obgyn = await conn.fetchval(
        "SELECT id FROM public.doctors WHERE specialty = 'obgyn' LIMIT 1"
    )
    if not ortho or not obgyn:
        pytest.skip("need both an ortho and an obgyn doctor")
    p = await patients_svc.create(conn, PatientCreate(first_name="L", phone="9000000050"), None)

    # Ortho surgeon in the Labor Room -> rejected
    with pytest.raises(AppError) as exc:
        await ot_svc.add(conn, OTCaseCreate(
            theatre_id=labor["id"], case_date=TEST_DATE, patient_id=p["id"],
            surgeon_id=ortho, procedure="ORIF"), None)
    assert exc.value.status_code == 422

    # OB-GYN surgeon in the Labor Room -> allowed
    case = await ot_svc.add(conn, OTCaseCreate(
        theatre_id=labor["id"], case_date=TEST_DATE, patient_id=p["id"],
        surgeon_id=obgyn, procedure="Normal delivery"), None)
    assert case["position"] == 1


# --- Inpatient beds: admit -> transfer -> discharge --------------------------
async def test_bed_admission_lifecycle(conn):
    from app.schemas.bed import AdmissionCreate, DischargeRequest, TransferRequest
    from app.services import beds as beds_svc

    free = await conn.fetch(
        "SELECT id FROM public.beds WHERE status = 'available' AND is_active = true "
        "ORDER BY id LIMIT 2"
    )
    if len(free) < 2:
        pytest.skip("need two available beds (run migration 010)")
    bed_a, bed_b = free[0]["id"], free[1]["id"]
    p = await patients_svc.create(conn, PatientCreate(first_name="Adm", phone="9000000060"), None)

    # admit -> bed occupied
    b = await beds_svc.admit(conn, AdmissionCreate(patient_id=p["id"], bed_id=bed_a), None)
    assert b["status"] == "occupied"
    adm_id = b["admission_id"]

    # admitting another patient to the same bed -> blocked
    p2 = await patients_svc.create(conn, PatientCreate(first_name="Adm2", phone="9000000061"), None)
    with pytest.raises(AppError) as exc:
        await beds_svc.admit(conn, AdmissionCreate(patient_id=p2["id"], bed_id=bed_a), None)
    assert exc.value.status_code == 409

    # transfer to bed_b -> old free, new occupied
    b2 = await beds_svc.transfer(conn, adm_id, TransferRequest(to_bed_id=bed_b), None)
    assert b2["id"] == bed_b and b2["status"] == "occupied"
    assert (await beds_svc.get_bed(conn, bed_a))["status"] == "available"

    # discharge -> bed freed
    b3 = await beds_svc.discharge(conn, adm_id, DischargeRequest(discharge_summary="ok"), None)
    assert b3["status"] == "available"


# --- Billing edge cases ------------------------------------------------------
async def test_billing_discount_clamps_to_zero(conn):
    from app.services import billing as bill
    from app.schemas.billing import DiscountUpdate
    p = await patients_svc.create(conn, PatientCreate(first_name="D", phone="9000000070"), None)
    inv = await bill.create_invoice(conn, InvoiceCreate(patient_id=p["id"]), None)
    inv = await bill.add_line_item(conn, inv["id"], LineItemCreate(description="x", unit_price=Decimal("100")), None)
    inv = await bill.set_discount(conn, inv["id"], DiscountUpdate(discount=Decimal("200")), None)
    assert Decimal(inv["grand_total"]) == Decimal("0")


async def test_billing_finalize_empty_rejected(conn):
    from app.services import billing as bill
    p = await patients_svc.create(conn, PatientCreate(first_name="E", phone="9000000071"), None)
    inv = await bill.create_invoice(conn, InvoiceCreate(patient_id=p["id"]), None)
    with pytest.raises(AppError) as exc:
        await bill.finalize_invoice(conn, inv["id"], None)
    assert exc.value.status_code == 422


async def test_billing_cancel_blocks_payment(conn):
    from app.services import billing as bill
    p = await patients_svc.create(conn, PatientCreate(first_name="C", phone="9000000072"), None)
    inv = await bill.create_invoice(conn, InvoiceCreate(patient_id=p["id"]), None)
    inv = await bill.add_line_item(conn, inv["id"], LineItemCreate(description="x", unit_price=Decimal("50")), None)
    inv = await bill.finalize_invoice(conn, inv["id"], None)
    inv = await bill.cancel_invoice(conn, inv["id"], None)
    assert inv["status"] == "cancelled"
    with pytest.raises(AppError) as exc:
        await bill.add_payment(conn, inv["id"], PaymentCreate(amount=Decimal("10")), None)
    assert exc.value.status_code == 422


async def test_billing_remove_line_item_recomputes(conn):
    from app.services import billing as bill
    p = await patients_svc.create(conn, PatientCreate(first_name="R", phone="9000000073"), None)
    inv = await bill.create_invoice(conn, InvoiceCreate(patient_id=p["id"]), None)
    inv = await bill.add_line_item(conn, inv["id"], LineItemCreate(description="a", unit_price=Decimal("100")), None)
    inv = await bill.add_line_item(conn, inv["id"], LineItemCreate(description="b", unit_price=Decimal("40")), None)
    assert Decimal(inv["subtotal"]) == Decimal("140")
    inv = await bill.remove_line_item(conn, inv["id"], inv["line_items"][0]["id"], None)
    assert Decimal(inv["subtotal"]) == Decimal("40")


async def test_billing_fractional_quantity(conn):
    from app.services import billing as bill
    p = await patients_svc.create(conn, PatientCreate(first_name="F", phone="9000000074"), None)
    inv = await bill.create_invoice(conn, InvoiceCreate(patient_id=p["id"]), None)
    inv = await bill.add_line_item(conn, inv["id"], LineItemCreate(
        description="x", quantity=Decimal("1.5"), unit_price=Decimal("100")), None)
    assert Decimal(inv["line_items"][0]["line_total"]) == Decimal("150.00")


# --- Bed edge cases ----------------------------------------------------------
async def _free_beds(conn, n):
    rows = await conn.fetch(
        "SELECT id FROM public.beds WHERE status='available' AND is_active=true "
        "ORDER BY id LIMIT $1", n)
    return [r["id"] for r in rows]


async def test_bed_admit_nonexistent_bed(conn):
    from app.services import beds as beds_svc
    from app.schemas.bed import AdmissionCreate
    p = await patients_svc.create(conn, PatientCreate(first_name="N", phone="9000000075"), None)
    with pytest.raises(AppError) as exc:
        await beds_svc.admit(conn, AdmissionCreate(patient_id=p["id"], bed_id=99999999), None)
    assert exc.value.status_code == 404


async def test_bed_transfer_same_bed_rejected(conn):
    from app.services import beds as beds_svc
    from app.schemas.bed import AdmissionCreate, TransferRequest
    beds = await _free_beds(conn, 1)
    if not beds:
        pytest.skip("no free bed")
    p = await patients_svc.create(conn, PatientCreate(first_name="S", phone="9000000076"), None)
    b = await beds_svc.admit(conn, AdmissionCreate(patient_id=p["id"], bed_id=beds[0]), None)
    with pytest.raises(AppError) as exc:
        await beds_svc.transfer(conn, b["admission_id"], TransferRequest(to_bed_id=beds[0]), None)
    assert exc.value.status_code == 422


async def test_bed_discharge_twice_rejected(conn):
    from app.services import beds as beds_svc
    from app.schemas.bed import AdmissionCreate, DischargeRequest
    beds = await _free_beds(conn, 1)
    if not beds:
        pytest.skip("no free bed")
    p = await patients_svc.create(conn, PatientCreate(first_name="D2", phone="9000000077"), None)
    b = await beds_svc.admit(conn, AdmissionCreate(patient_id=p["id"], bed_id=beds[0]), None)
    await beds_svc.discharge(conn, b["admission_id"], DischargeRequest(), None)
    with pytest.raises(AppError) as exc:
        await beds_svc.discharge(conn, b["admission_id"], DischargeRequest(), None)
    assert exc.value.status_code == 422


async def test_bed_transfer_to_occupied_rejected(conn):
    from app.services import beds as beds_svc
    from app.schemas.bed import AdmissionCreate, TransferRequest
    beds = await _free_beds(conn, 2)
    if len(beds) < 2:
        pytest.skip("need two free beds")
    p1 = await patients_svc.create(conn, PatientCreate(first_name="O1", phone="9000000078"), None)
    p2 = await patients_svc.create(conn, PatientCreate(first_name="O2", phone="9000000079"), None)
    adm1 = await beds_svc.admit(conn, AdmissionCreate(patient_id=p1["id"], bed_id=beds[0]), None)
    await beds_svc.admit(conn, AdmissionCreate(patient_id=p2["id"], bed_id=beds[1]), None)
    with pytest.raises(AppError) as exc:
        await beds_svc.transfer(conn, adm1["admission_id"], TransferRequest(to_bed_id=beds[1]), None)
    assert exc.value.status_code == 409


# --- OT edge cases -----------------------------------------------------------
async def test_ot_move_up_at_top_is_noop(conn):
    did = await _first_doctor(conn)
    tid = await conn.fetchval(
        "SELECT id FROM public.operation_theatres WHERE obgyn_only = false LIMIT 1")
    if not tid:
        pytest.skip("no unrestricted theatre")
    pa = await patients_svc.create(conn, PatientCreate(first_name="M1", phone="9000000080"), None)
    pb = await patients_svc.create(conn, PatientCreate(first_name="M2", phone="9000000081"), None)
    c1 = await ot_svc.add(conn, OTCaseCreate(theatre_id=tid, case_date=TEST_DATE, patient_id=pa["id"], surgeon_id=did, procedure="A"), None)
    await ot_svc.add(conn, OTCaseCreate(theatre_id=tid, case_date=TEST_DATE, patient_id=pb["id"], surgeon_id=did, procedure="B"), None)
    moved = await ot_svc.move(conn, c1["id"], OTMove(direction="up"), None)
    assert moved["position"] == 1  # already first, no change


async def test_ot_surgeon_filter_includes_covered(conn):
    hetal = await conn.fetchval("SELECT id FROM public.doctors WHERE full_name='Dr. Hetal Desai'")
    pallavi = await conn.fetchval("SELECT id FROM public.doctors WHERE full_name='Dr. Pallavi N. Patel'")
    if not hetal or not pallavi:
        pytest.skip("doctors missing")
    if await conn.fetchval("SELECT covers_for_doctor_id FROM public.doctors WHERE id=$1", pallavi) != hetal:
        pytest.skip("coverage not configured")
    tid = await conn.fetchval("SELECT id FROM public.operation_theatres LIMIT 1")
    p = await patients_svc.create(conn, PatientCreate(first_name="OC", phone="9000000082"), None)
    await ot_svc.add(conn, OTCaseCreate(theatre_id=tid, case_date=TEST_DATE, patient_id=p["id"], surgeon_id=hetal, procedure="LSCS"), None)
    covered = await ot_svc.list_cases(conn, TEST_DATE, None, pallavi)
    assert any(c["surgeon_id"] == hetal for c in covered)


# --- Queue edge cases --------------------------------------------------------
async def test_queue_cancelled_excluded_no_show_included(conn):
    did = await _first_doctor(conn)
    p1 = await patients_svc.create(conn, PatientCreate(first_name="Q1", phone="9000000083"), None)
    p2 = await patients_svc.create(conn, PatientCreate(first_name="Q2", phone="9000000084"), None)
    e1 = await queue_svc.add(conn, QueueAdd(doctor_id=did, patient_id=p1["id"], queue_date=TEST_DATE, check_in=True), None)
    e2 = await queue_svc.add(conn, QueueAdd(doctor_id=did, patient_id=p2["id"], queue_date=TEST_DATE, check_in=True), None)
    await queue_svc.update_status(conn, e1["id"], QueueStatusUpdate(status="cancelled"), None)
    await queue_svc.update_status(conn, e2["id"], QueueStatusUpdate(status="no_show"), None)
    ids = {x["id"] for x in await queue_svc.list_queue(conn, TEST_DATE, did)}
    assert e1["id"] not in ids
    assert e2["id"] in ids


async def test_queue_tokens_independent_per_doctor(conn):
    docs = await conn.fetch("SELECT id FROM public.doctors WHERE is_active=true ORDER BY id LIMIT 2")
    if len(docs) < 2:
        pytest.skip("need two doctors")
    p1 = await patients_svc.create(conn, PatientCreate(first_name="T1", phone="9000000085"), None)
    p2 = await patients_svc.create(conn, PatientCreate(first_name="T2", phone="9000000086"), None)
    e1 = await queue_svc.add(conn, QueueAdd(doctor_id=docs[0]["id"], patient_id=p1["id"], queue_date=TEST_DATE, check_in=True), None)
    e2 = await queue_svc.add(conn, QueueAdd(doctor_id=docs[1]["id"], patient_id=p2["id"], queue_date=TEST_DATE, check_in=True), None)
    assert e1["token_no"] == 1 and e2["token_no"] == 1


# --- Patient edge cases ------------------------------------------------------
async def test_patient_uhid_format(conn):
    import re
    p = await patients_svc.create(conn, PatientCreate(first_name="U", phone="9000000087"), None)
    assert re.match(r"^HMS-\d{4}-\d{6}$", p["uhid"])


async def test_patient_update_preserves_other_fields(conn):
    from app.schemas.patient import PatientUpdate
    p = await patients_svc.create(conn, PatientCreate(first_name="Keep", phone="9000000088"), None)
    updated = await patients_svc.update(conn, p["id"], PatientUpdate(address="New Rd"), None)
    assert updated["address"] == "New Rd"
    assert updated["phone"] == "9000000088"
    assert updated["first_name"] == "Keep"


# --- Billing: invoice -> item -> finalize -> pay (case: money flow) ----------
async def test_invoice_lifecycle(conn):
    from app.services import billing as bill
    p = await patients_svc.create(conn, PatientCreate(first_name="Bill", phone="9000000040"), None)

    inv = await bill.create_invoice(conn, InvoiceCreate(patient_id=p["id"]), None)
    assert inv["status"] == "draft"
    assert inv["invoice_no"] is None

    # add two items: 2 x 300 (no tax) + 1 x 100 @ 5% gst
    inv = await bill.add_line_item(conn, inv["id"], LineItemCreate(
        description="Consultation", quantity=Decimal("2"),
        unit_price=Decimal("300"), gst_rate=Decimal("0")), None)
    inv = await bill.add_line_item(conn, inv["id"], LineItemCreate(
        description="Consumable", quantity=Decimal("1"),
        unit_price=Decimal("100"), gst_rate=Decimal("5")), None)
    assert Decimal(inv["subtotal"]) == Decimal("700.00")
    assert Decimal(inv["tax_total"]) == Decimal("5.00")
    assert Decimal(inv["grand_total"]) == Decimal("705.00")

    # can't pay a draft
    with pytest.raises(AppError):
        await bill.add_payment(conn, inv["id"], PaymentCreate(amount=Decimal("100")), None)

    # finalize assigns a number and locks
    inv = await bill.finalize_invoice(conn, inv["id"], None)
    assert inv["status"] == "finalized"
    assert inv["invoice_no"] and inv["invoice_no"].startswith("INV-")

    # can't add items after finalize
    with pytest.raises(AppError):
        await bill.add_line_item(conn, inv["id"], LineItemCreate(
            description="Late", unit_price=Decimal("10")), None)

    # partial then full payment
    inv = await bill.add_payment(conn, inv["id"], PaymentCreate(amount=Decimal("200"), method="cash"), None)
    assert inv["status"] == "partially_paid"
    # overpayment rejected
    with pytest.raises(AppError):
        await bill.add_payment(conn, inv["id"], PaymentCreate(amount=Decimal("999")), None)
    inv = await bill.add_payment(conn, inv["id"], PaymentCreate(amount=Decimal("505"), method="upi"), None)
    assert inv["status"] == "paid"
    assert Decimal(inv["amount_paid"]) == Decimal("705.00")
