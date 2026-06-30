"""Pydantic schemas for OT (operation theatre) scheduling."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class OTCaseCreate(BaseModel):
    theatre_id: int
    case_date: date
    patient_id: int
    surgeon_id: int
    procedure: str = Field(min_length=1, max_length=200)
    notes: str | None = None


class OTStatusUpdate(BaseModel):
    status: Literal["scheduled", "in_progress", "completed", "cancelled"]


class OTMove(BaseModel):
    direction: Literal["up", "down"]
