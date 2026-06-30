"""Unit tests for patient schema validation (no DB required)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.patient import PatientCreate, PatientUpdate


def test_valid_patient():
    p = PatientCreate(first_name="Asha", phone="9876543210", gender="F")
    assert p.phone == "9876543210"
    assert p.gender == "F"


def test_phone_strips_country_code_and_spaces():
    p = PatientCreate(first_name="Ravi", phone="+91 98765 43210")
    assert p.phone == "9876543210"


def test_phone_strips_leading_zero():
    p = PatientCreate(first_name="Ravi", phone="098765 43210")
    assert p.phone == "9876543210"


def test_invalid_phone_rejected():
    with pytest.raises(ValidationError):
        PatientCreate(first_name="Ravi", phone="12345")  # too short / bad prefix


def test_future_dob_rejected():
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError):
        PatientCreate(first_name="Ravi", phone="9876543210", dob=tomorrow)


def test_missing_first_name_rejected():
    with pytest.raises(ValidationError):
        PatientCreate(first_name="", phone="9876543210")


def test_invalid_gender_rejected():
    with pytest.raises(ValidationError):
        PatientCreate(first_name="Ravi", phone="9876543210", gender="X")


def test_update_allows_partial_fields():
    u = PatientUpdate(address="New address")
    data = u.model_dump(exclude_unset=True)
    assert data == {"address": "New address"}


def test_update_validates_phone_when_present():
    with pytest.raises(ValidationError):
        PatientUpdate(phone="000")


def test_long_first_name_rejected():
    with pytest.raises(ValidationError):
        PatientCreate(first_name="A" * 101, phone="9876543210")


def test_blood_group_too_long_rejected():
    # max_length is 5; 6+ chars must be rejected ("O+", "AB-" etc. are fine).
    with pytest.raises(ValidationError):
        PatientCreate(first_name="Ravi", phone="9876543210", blood_group="ABNORM")


def test_special_chars_in_name_accepted():
    # Schema does NOT sanitize — XSS/quotes are stored literally and escaped at
    # render time by React. Confirm they pass validation unchanged.
    p = PatientCreate(first_name="O'Brien <script>", last_name="ડેસાઈ", phone="9876543210")
    assert p.first_name == "O'Brien <script>"
    assert p.last_name == "ડેસાઈ"


def test_phone_with_country_code_no_spaces():
    p = PatientCreate(first_name="A", phone="+919876543210")
    assert p.phone == "9876543210"


def test_error_envelope_serializes_dates():
    """A 409 duplicate response embeds patient records (with date fields) in
    `fields`; the envelope must be JSON-serializable."""
    import json
    from datetime import date, datetime

    from app.errors import _envelope

    env = _envelope(
        "DUPLICATE_PATIENT",
        "exists",
        fields={"duplicates": [{"dob": date(1990, 1, 1), "created_at": datetime.now()}]},
    )
    # Should not raise — dates are encoded to ISO strings.
    json.dumps(env)
    assert env["error"]["code"] == "DUPLICATE_PATIENT"
