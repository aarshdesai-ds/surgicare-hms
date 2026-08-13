"""Online payment endpoints: Razorpay payment links + webhook."""

from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, Depends, Request, Response

from ..auth import CurrentUser, get_current_user, require_roles
from ..config import settings
from ..database import require_pool
from ..integrations import razorpay_client
from ..schemas.billing import PaymentLinkCreate
from ..services import payments as service

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api", tags=["payments"])

_BILLERS = require_roles("billing", "admin", "reception")


@router.get("/payments/config")
async def payments_config(_: CurrentUser = Depends(get_current_user)) -> dict:
    """Lets the frontend show/hide the online-payment UI."""
    return {"razorpay_enabled": razorpay_client.is_configured()}


@router.post("/invoices/{invoice_id}/payment-link", status_code=201)
async def create_payment_link(
    invoice_id: int,
    payload: PaymentLinkCreate | None = None,
    user: CurrentUser = Depends(_BILLERS),
) -> dict:
    pool = require_pool()
    amount = payload.amount if payload else None
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.create_payment_link(conn, invoice_id, amount, user.id)


@router.get("/invoices/{invoice_id}/payment-link")
async def get_payment_link(
    invoice_id: int, _: CurrentUser = Depends(get_current_user)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return {"link": await service.latest_link(conn, invoice_id)}


@router.post("/invoices/{invoice_id}/payment-link/sync")
async def sync_payment_link(
    invoice_id: int, user: CurrentUser = Depends(_BILLERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.sync_link(conn, invoice_id, user.id)


@router.post("/webhooks/razorpay", include_in_schema=False)
async def razorpay_webhook(request: Request) -> Response:
    """Razorpay server-to-server settlement callback.

    Public (no bearer auth) — authenticity is proven by the HMAC signature in
    the X-Razorpay-Signature header, checked against RAZORPAY_WEBHOOK_SECRET.
    """
    raw = await request.body()
    signature = request.headers.get("x-razorpay-signature")
    if not razorpay_client.verify_webhook_signature(raw, signature):
        log.warning("razorpay.webhook.bad_signature")
        return Response(status_code=400)

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return Response(status_code=400)

    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await service.handle_webhook_event(conn, event)
    # Always 200 on a verified, well-formed event so Razorpay stops retrying.
    return Response(status_code=200)
