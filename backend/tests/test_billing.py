"""Unit tests for billing schemas (no DB)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.billing import (
    LineItemCreate, PaymentCreate, ServiceCreate,
)


def test_service_defaults():
    s = ServiceCreate(name="Consultation")
    assert s.unit_price == Decimal("0")
    assert s.category == "other"


def test_service_negative_price_rejected():
    with pytest.raises(ValidationError):
        ServiceCreate(name="X", unit_price=Decimal("-1"))


def test_gst_over_100_rejected():
    with pytest.raises(ValidationError):
        ServiceCreate(name="X", gst_rate=Decimal("120"))


def test_line_item_requires_positive_qty():
    with pytest.raises(ValidationError):
        LineItemCreate(description="X", quantity=Decimal("0"), unit_price=Decimal("10"))


def test_payment_must_be_positive():
    with pytest.raises(ValidationError):
        PaymentCreate(amount=Decimal("0"))


def test_payment_method_validated():
    with pytest.raises(ValidationError):
        PaymentCreate(amount=Decimal("100"), method="crypto")
