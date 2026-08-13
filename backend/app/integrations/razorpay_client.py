"""Thin async client for the Razorpay Payment Links API.

Kept deliberately small: we only need to create a link, fetch its status, and
verify webhook signatures. Uses httpx (already a dependency) rather than the
official SDK so calls stay non-blocking and no new package is required.

Docs: https://razorpay.com/docs/api/payments/payment-links/
"""

from __future__ import annotations

import hashlib
import hmac

import httpx

from ..config import settings
from ..errors import AppError

_BASE_URL = "https://api.razorpay.com/v1"
_TIMEOUT = httpx.Timeout(15.0)


def is_configured() -> bool:
    return settings.razorpay_configured


def _auth() -> tuple[str, str]:
    return (settings.razorpay_key_id, settings.razorpay_key_secret)


def _require_configured() -> None:
    if not is_configured():
        raise AppError(
            "PAYMENTS_UNCONFIGURED",
            "Online payments are not configured. Set RAZORPAY_KEY_ID and "
            "RAZORPAY_KEY_SECRET in the backend .env.",
            status_code=503,
        )


async def create_payment_link(
    *,
    amount_paise: int,
    description: str,
    reference_id: str,
    customer: dict,
    notes: dict,
    callback_url: str,
) -> dict:
    """Create a Razorpay payment link. Returns the raw link entity."""
    _require_configured()
    body = {
        "amount": amount_paise,
        "currency": "INR",
        "accept_partial": False,
        "description": description[:2048],
        "reference_id": reference_id,
        "customer": customer,
        "notify": {"sms": bool(customer.get("contact")), "email": False},
        "reminder_enable": True,
        "notes": notes,
        "callback_url": callback_url,
        "callback_method": "get",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(f"{_BASE_URL}/payment_links", json=body, auth=_auth())
    except httpx.HTTPError as exc:
        raise AppError("PAYMENTS_UPSTREAM", "Could not reach Razorpay.",
                       status_code=502) from exc
    return _handle_response(resp)


async def fetch_payment_link(link_id: str) -> dict:
    """Fetch a payment link's current state from Razorpay."""
    _require_configured()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_BASE_URL}/payment_links/{link_id}", auth=_auth())
    except httpx.HTTPError as exc:
        raise AppError("PAYMENTS_UPSTREAM", "Could not reach Razorpay.",
                       status_code=502) from exc
    return _handle_response(resp)


def _handle_response(resp: httpx.Response) -> dict:
    if resp.status_code >= 400:
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("description", "")
        except Exception:  # noqa: BLE001 - upstream body may not be JSON
            detail = resp.text[:200]
        raise AppError(
            "PAYMENTS_UPSTREAM",
            f"Razorpay error: {detail or resp.status_code}",
            status_code=502,
        )
    return resp.json()


def verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    """Verify the X-Razorpay-Signature header against the webhook secret.

    Returns False (rather than raising) so the caller decides the HTTP response.
    """
    secret = settings.razorpay_webhook_secret
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
