"""Unit tests for staff-update schema (no DB)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.staff import StaffUpdate


def test_role_only():
    assert StaffUpdate(role="doctor").role == "doctor"


def test_active_only():
    assert StaffUpdate(is_active=False).is_active is False


def test_empty_rejected():
    with pytest.raises(ValidationError):
        StaffUpdate()


def test_invalid_role_rejected():
    with pytest.raises(ValidationError):
        StaffUpdate(role="superadmin")


def test_create_valid():
    from app.schemas.staff import StaffCreate
    s = StaffCreate(email="Nurse@Hospital.LOCAL", password="secret1", role="nurse")
    assert s.email == "nurse@hospital.local"  # normalized
    assert s.role == "nurse"


def test_create_bad_email():
    from app.schemas.staff import StaffCreate
    with pytest.raises(ValidationError):
        StaffCreate(email="not-an-email", password="secret1")


def test_create_short_password():
    from app.schemas.staff import StaffCreate
    with pytest.raises(ValidationError):
        StaffCreate(email="a@b.com", password="123")
