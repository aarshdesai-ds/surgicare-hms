"""Pydantic schemas for inpatient admissions."""

from __future__ import annotations

from pydantic import BaseModel


class AdmissionCreate(BaseModel):
    patient_id: int
    bed_id: int
    attending_doctor_id: int | None = None
    diagnosis: str | None = None


class TransferRequest(BaseModel):
    to_bed_id: int


class DischargeRequest(BaseModel):
    discharge_summary: str | None = None
