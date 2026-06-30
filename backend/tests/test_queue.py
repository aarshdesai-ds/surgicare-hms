"""Unit tests for OPD session + queue schemas (no DB required)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.queue import QueueAdd, QueueStatusUpdate, SessionUpsert


def test_session_valid():
    s = SessionUpsert(
        doctor_id=1, session_date="2026-07-01", start_time="10:00", end_time="13:00"
    )
    assert s.start_time.hour == 10
    assert s.end_time.hour == 13


def test_session_end_before_start_rejected():
    with pytest.raises(ValidationError):
        SessionUpsert(
            doctor_id=1, session_date="2026-07-01",
            start_time="13:00", end_time="10:00",
        )


def test_queue_add_defaults_to_not_checked_in():
    q = QueueAdd(doctor_id=1, patient_id=2, queue_date="2026-07-01")
    assert q.check_in is False


def test_queue_add_walk_in():
    q = QueueAdd(doctor_id=1, patient_id=2, queue_date="2026-07-01", check_in=True)
    assert q.check_in is True


def test_queue_status_valid():
    assert QueueStatusUpdate(status="in_consultation").status == "in_consultation"


def test_queue_status_invalid_rejected():
    with pytest.raises(ValidationError):
        QueueStatusUpdate(status="seen")
