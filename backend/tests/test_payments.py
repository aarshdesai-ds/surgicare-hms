"""Tests for Razorpay payment links.

Unit tests (no DB): amount conversion, webhook signature verification, the
webhook's bad-signature rejection, and the config endpoint.

Integration tests (DB, gated on TEST_DATABASE_URL): create a link against a
finalized invoice with the Razorpay network calls monkeypatched, then reconcile
via both the poll and the webhook — asserting the payment is recorded exactly
once.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal

import pytest

from app.auth import CurrentUser, get_current_user
from app.integrations import razorpay_client
from app.main import create_app
from app.schemas.billing import PaymentLinkCreate
from app.services import payments as pay


# --------------------------- unit: no database ---------------------------
def test_paise_conversion():
    assert pay._paise(Decimal("500")) == 50000
    assert pay._paise(Decimal("500.50")) == 50050
    assert pay._paise(Decimal("0.01")) == 1


def test_payment_link_amount_optional():
    assert PaymentLinkCreate().amount is None
    assert PaymentLinkCreate(amount=Decimal("100")).amount == Decimal("100")


def test_payment_link_amount_must_be_positive():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        PaymentLinkCreate(amount=Decimal("0"))


def test_verify_webhook_signature_roundtrip(monkeypatch):
    secret = "whsec_test"
    monkeypatch.setattr(razorpay_client.settings, "razorpay_webhook_secret", secret)
    body = b'{"event":"payment_link.paid"}'
    good = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert razorpay_client.verify_webhook_signature(body, good) is True
    assert razorpay_client.verify_webhook_signature(body, "deadbeef") is False
    assert razorpay_client.verify_webhook_signature(body, None) is False


def test_verify_webhook_signature_no_secret(monkeypatch):
    monkeypatch.setattr(razorpay_client.settings, "razorpay_webhook_secret", "")
    body = b"{}"
    sig = hmac.new(b"x", body, hashlib.sha256).hexdigest()
    # With no secret configured we cannot trust anything → always False.
    assert razorpay_client.verify_webhook_signature(body, sig) is False


def test_is_configured_reflects_keys(monkeypatch):
    monkeypatch.setattr(razorpay_client.settings, "razorpay_key_id", "")
    monkeypatch.setattr(razorpay_client.settings, "razorpay_key_secret", "")
    assert razorpay_client.is_configured() is False
    monkeypatch.setattr(razorpay_client.settings, "razorpay_key_id", "rzp_test_x")
    monkeypatch.setattr(razorpay_client.settings, "razorpay_key_secret", "secret")
    assert razorpay_client.is_configured() is True


def test_webhook_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setattr(razorpay_client.settings, "razorpay_webhook_secret", "whsec_test")
    resp = client.post(
        "/api/webhooks/razorpay",
        content=b'{"event":"payment_link.paid"}',
        headers={"X-Razorpay-Signature": "not-valid"},
    )
    assert resp.status_code == 400


def test_config_endpoint_reports_disabled(monkeypatch):
    monkeypatch.setattr(razorpay_client.settings, "razorpay_key_id", "")
    monkeypatch.setattr(razorpay_client.settings, "razorpay_key_secret", "")
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="u1", role="admin")
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        resp = c.get("/api/payments/config")
    assert resp.status_code == 200
    assert resp.json() == {"razorpay_enabled": False}


# --------------------------- integration: DB ---------------------------
pytest_plugins: list = []


async def _finalized_invoice(conn) -> tuple[int, Decimal]:
    """Create a patient + finalized invoice with a single ₹500 line. Returns
    (invoice_id, grand_total)."""
    from app.schemas.billing import InvoiceCreate, LineItemCreate
    from app.schemas.patient import PatientCreate
    from app.services import billing, patients as patients_svc

    p = await patients_svc.create(
        conn, PatientCreate(first_name="Pay", phone="9111100001"), None
    )
    inv = await billing.create_invoice(conn, InvoiceCreate(patient_id=p["id"]), None)
    await billing.add_line_item(
        conn, inv["id"],
        LineItemCreate(description="Consult", quantity=Decimal("1"),
                       unit_price=Decimal("500"), gst_rate=Decimal("0")),
        None,
    )
    fin = await billing.finalize_invoice(conn, inv["id"], None)
    return fin["id"], Decimal(fin["grand_total"])


@pytest.mark.asyncio
async def test_create_and_sync_payment_link(conn, monkeypatch):
    async def fake_create(**kwargs):
        return {"id": "plink_sync1", "short_url": "https://rzp.io/i/sync1", "status": "created"}

    async def fake_fetch(link_id):
        return {"id": link_id, "status": "paid",
                "payments": [{"payment_id": "pay_sync1", "status": "captured"}]}

    monkeypatch.setattr(pay.razorpay_client, "is_configured", lambda: True)
    monkeypatch.setattr(pay.razorpay_client, "create_payment_link", fake_create)
    monkeypatch.setattr(pay.razorpay_client, "fetch_payment_link", fake_fetch)

    inv_id, total = await _finalized_invoice(conn)

    created = await pay.create_payment_link(conn, inv_id, None, None)
    assert created["link"]["provider_link_id"] == "plink_sync1"
    assert created["link"]["short_url"].endswith("sync1")
    assert created["link"]["status"] == "created"

    # First sync settles the invoice.
    synced = await pay.sync_link(conn, inv_id, None)
    assert synced["link"]["status"] == "paid"
    assert Decimal(synced["invoice"]["amount_paid"]) == total
    assert synced["invoice"]["status"] == "paid"

    # Second sync is a no-op — no double payment.
    again = await pay.sync_link(conn, inv_id, None)
    assert Decimal(again["invoice"]["amount_paid"]) == total
    n = await conn.fetchval(
        "SELECT COUNT(*) FROM public.payments WHERE invoice_id = $1", inv_id
    )
    assert n == 1


@pytest.mark.asyncio
async def test_webhook_reconciles_exactly_once(conn, monkeypatch):
    async def fake_create(**kwargs):
        return {"id": "plink_wh1", "short_url": "https://rzp.io/i/wh1", "status": "created"}

    monkeypatch.setattr(pay.razorpay_client, "is_configured", lambda: True)
    monkeypatch.setattr(pay.razorpay_client, "create_payment_link", fake_create)

    inv_id, total = await _finalized_invoice(conn)
    await pay.create_payment_link(conn, inv_id, None, None)

    event = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {"entity": {"id": "plink_wh1", "status": "paid"}},
            "payment": {"entity": {"id": "pay_wh1"}},
        },
    }
    await pay.handle_webhook_event(conn, event)
    await pay.handle_webhook_event(conn, event)  # duplicate delivery

    n = await conn.fetchval(
        "SELECT COUNT(*) FROM public.payments WHERE invoice_id = $1", inv_id
    )
    assert n == 1
    inv = await conn.fetchrow(
        "SELECT status, amount_paid FROM public.invoices WHERE id = $1", inv_id
    )
    assert inv["status"] == "paid"
    assert Decimal(inv["amount_paid"]) == total
