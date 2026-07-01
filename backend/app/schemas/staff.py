"""Pydantic schemas for staff (profile) management."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

_ROLE = Literal["admin", "doctor", "reception", "billing", "nurse"]
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class StaffUpdate(BaseModel):
    role: _ROLE | None = None
    is_active: bool | None = None
    full_name: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _need_something(self):
        if self.role is None and self.is_active is None and self.full_name is None:
            raise ValueError("provide role, is_active, and/or full_name to update")
        return self


class StaffCreate(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=72)
    full_name: str | None = Field(default=None, max_length=100)
    phone: str | None = None
    role: _ROLE = "reception"

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL.match(v):
            raise ValueError("enter a valid email address")
        return v
