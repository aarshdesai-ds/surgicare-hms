"""Unit tests for OT schemas (no DB required)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.ot import OTCaseCreate, OTMove, OTStatusUpdate


def test_case_valid():
    c = OTCaseCreate(
        theatre_id=1, case_date="2026-07-01", patient_id=2, surgeon_id=3,
        procedure="LSCS",
    )
    assert c.procedure == "LSCS"


def test_case_requires_procedure():
    with pytest.raises(ValidationError):
        OTCaseCreate(
            theatre_id=1, case_date="2026-07-01", patient_id=2, surgeon_id=3,
            procedure="",
        )


def test_status_valid():
    assert OTStatusUpdate(status="in_progress").status == "in_progress"


def test_status_invalid():
    with pytest.raises(ValidationError):
        OTStatusUpdate(status="postponed")


def test_move_direction():
    assert OTMove(direction="up").direction == "up"
    with pytest.raises(ValidationError):
        OTMove(direction="sideways")
