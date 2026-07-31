"""Pydantic schemas for prescriptions."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PrescriptionItemIn(BaseModel):
    drug_name: str = Field(min_length=1, max_length=200)
    strength: str | None = None
    frequency: str | None = None
    duration: str | None = None
    quantity: str | None = None
    instructions: str | None = None


class PrescriptionCreate(BaseModel):
    patient_id: int
    doctor_id: int | None = None
    encounter_id: int | None = None
    notes: str | None = None
    items: list[PrescriptionItemIn] = Field(min_length=1)
