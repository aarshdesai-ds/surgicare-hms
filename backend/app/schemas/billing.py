"""Pydantic schemas for billing: catalog, invoices, line items, payments."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

_CATEGORY = Literal["consultation", "procedure", "bed", "ot", "lab", "pharmacy", "other"]


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: _CATEGORY = "other"
    code: str | None = Field(default=None, max_length=30)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    gst_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    is_active: bool = True


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: _CATEGORY | None = None
    unit_price: Decimal | None = Field(default=None, ge=0)
    gst_rate: Decimal | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None


class InvoiceCreate(BaseModel):
    patient_id: int
    notes: str | None = None


class LineItemCreate(BaseModel):
    service_id: int | None = None
    description: str = Field(min_length=1, max_length=200)
    source: Literal["manual", "consultation", "bed", "ot", "pharmacy", "lab"] = "manual"
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal = Field(ge=0)
    gst_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class DiscountUpdate(BaseModel):
    discount: Decimal = Field(ge=0)


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    method: Literal["cash", "card", "upi", "netbanking", "razorpay", "other"] = "cash"
    reference: str | None = None


class PaymentLinkCreate(BaseModel):
    # Optional partial amount; defaults to the full amount due on the invoice.
    amount: Decimal | None = Field(default=None, gt=0)
