"""Pydantic schemas for patient registration and editing.

Validation rules:
- phone / alt_phone: normalized to a 10-digit Indian mobile number.
- dob: cannot be in the future.
- gender: M / F / O.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")


def _normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    # Accept a leading country code (+91 / 0091 / 91) and strip it.
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not _INDIAN_MOBILE.match(digits):
        raise ValueError("must be a valid 10-digit Indian mobile number")
    return digits


class PatientBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    dob: date | None = None
    gender: Literal["M", "F", "O"] | None = None
    phone: str
    alt_phone: str | None = None
    address: str | None = None
    blood_group: str | None = Field(default=None, max_length=5)
    abha_number: str | None = None
    allergies: str | None = None
    emergency_contact: dict | None = None

    @field_validator("phone", "alt_phone")
    @classmethod
    def _check_phone(cls, v: str | None) -> str | None:
        return _normalize_phone(v)

    @field_validator("dob")
    @classmethod
    def _check_dob(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("date of birth cannot be in the future")
        return v


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    """All fields optional; only provided fields are updated."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    dob: date | None = None
    gender: Literal["M", "F", "O"] | None = None
    phone: str | None = None
    alt_phone: str | None = None
    address: str | None = None
    blood_group: str | None = Field(default=None, max_length=5)
    abha_number: str | None = None
    allergies: str | None = None
    emergency_contact: dict | None = None

    @field_validator("phone", "alt_phone")
    @classmethod
    def _check_phone(cls, v: str | None) -> str | None:
        return _normalize_phone(v)

    @field_validator("dob")
    @classmethod
    def _check_dob(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("date of birth cannot be in the future")
        return v
