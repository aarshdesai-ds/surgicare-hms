"""Unit tests for encounter schema (no DB required)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.encounter import EncounterCreate


def test_encounter_with_diagnosis():
    e = EncounterCreate(patient_id=1, diagnosis="Fracture, left wrist")
    assert e.encounter_type == "opd"


def test_encounter_with_vitals_only():
    e = EncounterCreate(patient_id=1, vitals={"bp": "120/80", "pulse": "76"})
    assert e.vitals["bp"] == "120/80"


def test_empty_encounter_rejected():
    with pytest.raises(ValidationError):
        EncounterCreate(patient_id=1)


def test_invalid_type_rejected():
    with pytest.raises(ValidationError):
        EncounterCreate(patient_id=1, notes="x", encounter_type="lab")
