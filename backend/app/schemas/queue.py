"""Pydantic schemas for OPD sessions and the patient queue."""

from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, model_validator

QUEUE_STATUSES = (
    "booked",
    "waiting",
    "in_consultation",
    "completed",
    "no_show",
    "cancelled",
)


class SessionUpsert(BaseModel):
    doctor_id: int
    session_date: date
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _check_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class QueueAdd(BaseModel):
    doctor_id: int
    patient_id: int
    queue_date: date
    reason: str | None = None
    # True = walk-in who has arrived (check in immediately, gets a token).
    # False = pre-booked, not yet arrived.
    check_in: bool = False


class QueueStatusUpdate(BaseModel):
    status: Literal[
        "booked", "waiting", "in_consultation", "completed", "no_show", "cancelled"
    ]
