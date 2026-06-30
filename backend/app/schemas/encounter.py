"""Pydantic schemas for clinical encounters (consultation notes)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator


class EncounterCreate(BaseModel):
    patient_id: int
    doctor_id: int | None = None
    queue_entry_id: int | None = None
    encounter_type: Literal["opd", "ipd", "ot"] = "opd"
    vitals: dict | None = None          # {bp, pulse, temp, spo2, weight}
    complaints: str | None = None
    diagnosis: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _require_content(self):
        if not any([self.vitals, self.complaints, self.diagnosis, self.notes]):
            raise ValueError(
                "an encounter must include at least vitals, complaints, "
                "diagnosis, or notes"
            )
        return self
