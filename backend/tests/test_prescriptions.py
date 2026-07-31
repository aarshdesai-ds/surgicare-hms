"""Unit tests for prescription schemas (no DB)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.prescription import PrescriptionCreate, PrescriptionItemIn


def test_valid_prescription():
    rx = PrescriptionCreate(
        patient_id=1,
        items=[PrescriptionItemIn(drug_name="Paracetamol", strength="500mg",
                                  frequency="1-0-1", duration="5 days", quantity="10")],
    )
    assert rx.items[0].drug_name == "Paracetamol"


def test_prescription_requires_at_least_one_item():
    with pytest.raises(ValidationError):
        PrescriptionCreate(patient_id=1, items=[])


def test_item_requires_drug_name():
    with pytest.raises(ValidationError):
        PrescriptionItemIn(drug_name="")


def test_item_optional_fields_default_none():
    it = PrescriptionItemIn(drug_name="Amoxicillin")
    assert it.strength is None and it.frequency is None and it.quantity is None
