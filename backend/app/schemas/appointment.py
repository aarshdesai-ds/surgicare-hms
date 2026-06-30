"""Pydantic schemas for appointments."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

APPOINTMENT_STATUSES = (
    "booked",
    "checked_in",
    "in_progress",
    "completed",
    "cancelled",
    "no_show",
)


class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_id: int
    scheduled_at: datetime
    duration_min: int = Field(default=15, ge=5, le=480)
    reason: str | None = None


class AppointmentStatusUpdate(BaseModel):
    status: Literal[
        "booked", "checked_in", "in_progress", "completed", "cancelled", "no_show"
    ]
