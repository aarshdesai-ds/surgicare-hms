"""Edge-case unit tests (no DB): schema boundaries, RBAC, error envelopes.

These run everywhere. DB-behaviour edge cases live in test_integration.py.
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from pydantic import ValidationError

from app.auth import CurrentUser, get_current_user, require_roles
from app.config import settings
from app.errors import AppError
from app.schemas.bed import AdmissionCreate, DischargeRequest, TransferRequest
from app.schemas.billing import (
    DiscountUpdate, InvoiceCreate, LineItemCreate, PaymentCreate,
    ServiceCreate, ServiceUpdate,
)
from app.schemas.encounter import EncounterCreate
from app.schemas.ot import OTCaseCreate, OTMove, OTStatusUpdate
from app.schemas.patient import PatientCreate, PatientUpdate
from app.schemas.queue import QueueAdd, QueueStatusUpdate, SessionUpsert
from app.schemas.staff import StaffCreate, StaffUpdate


# ============================ Patients ============================
def test_phone_prefix_6_is_valid():
    assert PatientCreate(first_name="A", phone="6000000000").phone == "6000000000"


def test_phone_prefix_5_is_invalid():
    with pytest.raises(ValidationError):
        PatientCreate(first_name="A", phone="5000000000")


def test_phone_all_nines_valid():
    assert PatientCreate(first_name="A", phone="9999999999").phone == "9999999999"


def test_phone_with_dashes_normalized():
    assert PatientCreate(first_name="A", phone="98765-43210").phone == "9876543210"


def test_phone_with_parens_spaces_normalized():
    assert PatientCreate(first_name="A", phone="(98765) 43210").phone == "9876543210"


def test_phone_eleven_digits_no_leading_zero_invalid():
    with pytest.raises(ValidationError):
        PatientCreate(first_name="A", phone="98765432109")


def test_dob_year_1900_valid():
    assert PatientCreate(first_name="A", phone="9876543210", dob=date(1900, 1, 1)).dob


def test_blood_group_three_chars_valid():
    assert PatientCreate(first_name="A", phone="9876543210", blood_group="AB+").blood_group == "AB+"


def test_first_name_exactly_100_valid():
    assert PatientCreate(first_name="A" * 100, phone="9876543210")


def test_update_future_dob_invalid():
    with pytest.raises(ValidationError):
        PatientUpdate(dob=date.today() + timedelta(days=1))


# ============================ OPD sessions & queue ============================
def test_session_equal_times_invalid():
    with pytest.raises(ValidationError):
        SessionUpsert(doctor_id=1, session_date="2026-07-01", start_time="10:00", end_time="10:00")


def test_session_one_minute_window_valid():
    assert SessionUpsert(doctor_id=1, session_date="2026-07-01", start_time="09:00", end_time="09:01")


def test_queue_all_statuses_valid():
    for s in ("booked", "waiting", "in_consultation", "completed", "no_show", "cancelled"):
        assert QueueStatusUpdate(status=s).status == s


def test_queue_add_reason_optional():
    assert QueueAdd(doctor_id=1, patient_id=2, queue_date="2026-07-01").reason is None


# ============================ OT ============================
def test_ot_procedure_200_chars_valid():
    assert OTCaseCreate(theatre_id=1, case_date="2026-07-01", patient_id=1, surgeon_id=1, procedure="P" * 200)


def test_ot_procedure_201_chars_invalid():
    with pytest.raises(ValidationError):
        OTCaseCreate(theatre_id=1, case_date="2026-07-01", patient_id=1, surgeon_id=1, procedure="P" * 201)


def test_ot_move_invalid_direction():
    with pytest.raises(ValidationError):
        OTMove(direction="left")


def test_ot_all_statuses_valid():
    for s in ("scheduled", "in_progress", "completed", "cancelled"):
        assert OTStatusUpdate(status=s).status == s


# ============================ Encounters ============================
def test_encounter_complaints_only():
    assert EncounterCreate(patient_id=1, complaints="fever").complaints == "fever"


def test_encounter_notes_only():
    assert EncounterCreate(patient_id=1, notes="rest").notes == "rest"


def test_encounter_types_valid():
    for tp in ("opd", "ipd", "ot"):
        assert EncounterCreate(patient_id=1, notes="x", encounter_type=tp).encounter_type == tp


# ============================ Staff ============================
def test_staff_password_exactly_6_valid():
    assert StaffCreate(email="a@b.co", password="123456").password == "123456"


def test_staff_password_5_invalid():
    with pytest.raises(ValidationError):
        StaffCreate(email="a@b.co", password="12345")


def test_staff_password_72_valid_73_invalid():
    assert StaffCreate(email="a@b.co", password="x" * 72)
    with pytest.raises(ValidationError):
        StaffCreate(email="a@b.co", password="x" * 73)


def test_staff_email_uppercase_and_spaces_normalized():
    assert StaffCreate(email="  Doc@Hospital.LOCAL ", password="secret1").email == "doc@hospital.local"


def test_staff_update_full_name_only():
    assert StaffUpdate(full_name="Dr X").full_name == "Dr X"


def test_staff_update_role_and_active():
    u = StaffUpdate(role="nurse", is_active=False)
    assert u.role == "nurse" and u.is_active is False


# ============================ Billing ============================
def test_service_name_empty_invalid():
    with pytest.raises(ValidationError):
        ServiceCreate(name="")


def test_service_name_120_valid_121_invalid():
    assert ServiceCreate(name="A" * 120)
    with pytest.raises(ValidationError):
        ServiceCreate(name="A" * 121)


def test_service_gst_boundaries():
    assert ServiceCreate(name="X", gst_rate=Decimal("100"))
    assert ServiceCreate(name="X", gst_rate=Decimal("0"))
    with pytest.raises(ValidationError):
        ServiceCreate(name="X", gst_rate=Decimal("100.01"))


def test_service_update_partial():
    assert ServiceUpdate(unit_price=Decimal("250")).unit_price == Decimal("250")


def test_line_item_qty_negative_invalid():
    with pytest.raises(ValidationError):
        LineItemCreate(description="x", quantity=Decimal("-1"), unit_price=Decimal("10"))


def test_line_item_unit_price_zero_valid_negative_invalid():
    assert LineItemCreate(description="x", unit_price=Decimal("0"))
    with pytest.raises(ValidationError):
        LineItemCreate(description="x", unit_price=Decimal("-1"))


def test_line_item_description_empty_invalid():
    with pytest.raises(ValidationError):
        LineItemCreate(description="", unit_price=Decimal("10"))


def test_line_item_description_201_invalid():
    with pytest.raises(ValidationError):
        LineItemCreate(description="d" * 201, unit_price=Decimal("10"))


def test_payment_negative_invalid():
    with pytest.raises(ValidationError):
        PaymentCreate(amount=Decimal("-5"))


def test_payment_all_methods_valid():
    for m in ("cash", "card", "upi", "netbanking", "razorpay", "other"):
        assert PaymentCreate(amount=Decimal("100"), method=m).method == m


def test_discount_zero_valid_negative_invalid():
    assert DiscountUpdate(discount=Decimal("0")).discount == Decimal("0")
    with pytest.raises(ValidationError):
        DiscountUpdate(discount=Decimal("-1"))


def test_invoice_create_requires_patient():
    with pytest.raises(ValidationError):
        InvoiceCreate()


# ============================ Beds ============================
def test_admission_requires_bed():
    with pytest.raises(ValidationError):
        AdmissionCreate(patient_id=1)


def test_admission_optional_fields_default_none():
    a = AdmissionCreate(patient_id=1, bed_id=2)
    assert a.attending_doctor_id is None and a.diagnosis is None


def test_transfer_requires_bed():
    with pytest.raises(ValidationError):
        TransferRequest()


def test_discharge_summary_optional():
    assert DischargeRequest().discharge_summary is None
    assert DischargeRequest(discharge_summary="done").discharge_summary == "done"


# ============================ Auth / RBAC ============================
def _token(claims: dict) -> str:
    base = {"aud": "authenticated", "exp": int(time.time()) + 3600}
    return jwt.encode({**base, **claims}, settings.supabase_jwt_secret, algorithm="HS256")


def _creds(tok: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=tok)


async def test_wrong_audience_rejected():
    tok = jwt.encode(
        {"sub": "u1", "aud": "wrong", "exp": int(time.time()) + 3600},
        settings.supabase_jwt_secret, algorithm="HS256",
    )
    with pytest.raises(AppError) as exc:
        await get_current_user(_creds(tok))
    assert exc.value.status_code == 401


async def test_require_roles_multiple_allows_one():
    dep = require_roles("admin", "billing", "reception")
    assert (await dep(user=CurrentUser(id="x", role="billing"))).role == "billing"


async def test_require_roles_forbids_none_role():
    dep = require_roles("admin")
    with pytest.raises(AppError) as exc:
        await dep(user=CurrentUser(id="x", role=None))
    assert exc.value.status_code == 403


async def test_token_without_sub_yields_no_role():
    user = await get_current_user(_creds(_token({"email": "x@y.z"})))
    assert user.id == "" and user.role is None


# ============================ Error envelope (API) ============================
def _auth(role: str) -> dict:
    tok = _token({"sub": "t", "app_metadata": {"role": role}})
    return {"Authorization": f"Bearer {tok}"}


def test_create_service_forbidden_for_reception(client):
    r = client.post("/api/services", headers=_auth("reception"), json={"name": "X"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_ot_case_missing_fields_validation(client):
    r = client.post("/api/ot-cases", headers=_auth("admin"),
                    json={"theatre_id": 1, "case_date": "2026-07-01"})  # missing patient/surgeon/procedure
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_encounter_empty_content_rejected(client):
    r = client.post("/api/encounters", headers=_auth("admin"), json={"patient_id": 1})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_admission_requires_auth(client):
    r = client.post("/api/admissions", json={"patient_id": 1, "bed_id": 1})
    assert r.status_code == 401


def test_invoice_create_requires_auth(client):
    r = client.post("/api/invoices", json={"patient_id": 1})
    assert r.status_code == 401


def test_beds_list_requires_auth(client):
    assert client.get("/api/beds").status_code == 401
