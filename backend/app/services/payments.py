"""Online payment (Razorpay payment link) business logic.

Flow: create a link against a finalized invoice → patient pays on their phone
(UPI/card) → the invoice is settled either by the Razorpay webhook or by a
manual "check status" poll. Both paths converge on `_reconcile_paid`, which
records the payment exactly once (idempotent on the Razorpay payment id).
"""

from __future__ import annotations

from decimal import Decimal

import asyncpg

from ..config import settings
from ..errors import AppError
from ..integrations import razorpay_client
from ..utils.audit import write_audit
from . import billing


def _paise(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value())


async def _invoice_for_payment(conn: asyncpg.Connection, invoice_id: int) -> asyncpg.Record:
    inv = await conn.fetchrow(
        "SELECT id, invoice_no, patient_id, status, grand_total, amount_paid "
        "FROM public.invoices WHERE id = $1",
        invoice_id,
    )
    if inv is None:
        raise AppError("NOT_FOUND", "Invoice not found.", status_code=404)
    if inv["status"] in ("draft", "cancelled"):
        raise AppError(
            "NOT_PAYABLE",
            "Finalize the invoice before collecting an online payment.",
            status_code=422,
        )
    return inv


async def create_payment_link(
    conn: asyncpg.Connection, invoice_id: int, amount: Decimal | None, actor_id: str
) -> dict:
    inv = await _invoice_for_payment(conn, invoice_id)
    due = Decimal(inv["grand_total"]) - Decimal(inv["amount_paid"])
    if due <= 0:
        raise AppError("NOTHING_DUE", "This invoice is already fully paid.",
                       status_code=422)
    amount = due if amount is None else Decimal(amount)
    if amount <= 0 or amount > due:
        raise AppError(
            "INVALID_AMOUNT",
            f"Amount must be between 0 and the amount due ({due}).",
            status_code=422,
            fields={"due": str(due)},
        )

    # Insert first so we have a stable, unique reference_id for Razorpay and a
    # DB record even if the upstream call fails (the router's transaction rolls
    # both back together on error).
    link_row = await conn.fetchrow(
        "INSERT INTO public.payment_links (invoice_id, amount, created_by) "
        "VALUES ($1, $2, $3::uuid) RETURNING id",
        invoice_id, amount, actor_id,
    )
    link_id = link_row["id"]

    patient = await conn.fetchrow(
        "SELECT (first_name || ' ' || COALESCE(last_name,'')) AS name, phone "
        "FROM public.patients WHERE id = $1",
        inv["patient_id"],
    )
    label = inv["invoice_no"] or f"Invoice #{invoice_id}"
    link = await razorpay_client.create_payment_link(
        amount_paise=_paise(amount),
        description=f"{label} — SurgiCare Hospital",
        reference_id=f"hms-inv{invoice_id}-plink{link_id}",
        customer={
            "name": (patient["name"] or "Patient").strip(),
            "contact": patient["phone"] or "",
        },
        notes={"invoice_id": str(invoice_id), "payment_link_row": str(link_id)},
        callback_url=settings.razorpay_callback_url,
    )

    await conn.execute(
        "UPDATE public.payment_links SET provider_link_id = $1, short_url = $2, "
        "status = $3 WHERE id = $4",
        link["id"], link.get("short_url"), link.get("status", "created"), link_id,
    )
    await write_audit(conn, actor_id=actor_id, action="payment_link",
                      entity="invoices", entity_id=invoice_id,
                      detail={"amount": str(amount), "link_id": link["id"]})

    return {
        "invoice": await billing.get_invoice(conn, invoice_id),
        "link": await _get_link(conn, link_id),
    }


async def _get_link(conn: asyncpg.Connection, link_id: int) -> dict:
    row = await conn.fetchrow(
        "SELECT id, invoice_id, provider, provider_link_id, short_url, amount, "
        "status, provider_payment_id, created_at, paid_at "
        "FROM public.payment_links WHERE id = $1",
        link_id,
    )
    return dict(row) if row else None


async def latest_link(conn: asyncpg.Connection, invoice_id: int) -> dict | None:
    row = await conn.fetchrow(
        "SELECT id, invoice_id, provider, provider_link_id, short_url, amount, "
        "status, provider_payment_id, created_at, paid_at "
        "FROM public.payment_links WHERE invoice_id = $1 "
        "ORDER BY created_at DESC LIMIT 1",
        invoice_id,
    )
    return dict(row) if row else None


async def sync_link(conn: asyncpg.Connection, invoice_id: int, actor_id: str) -> dict:
    """Poll Razorpay for the latest link's status and reconcile if paid.

    This is the fallback that lets a payment settle in test/dev without a
    public webhook URL — reception clicks "Check status".
    """
    link = await latest_link(conn, invoice_id)
    if link is None:
        raise AppError("NOT_FOUND", "No payment link for this invoice.", status_code=404)
    if link["status"] == "paid":
        return {"invoice": await billing.get_invoice(conn, invoice_id), "link": link}

    remote = await razorpay_client.fetch_payment_link(link["provider_link_id"])
    status = remote.get("status")
    if status == "paid":
        payment_id = _first_payment_id(remote)
        await _reconcile_paid(conn, link, payment_id, actor_id)
    elif status in ("cancelled", "expired"):
        await conn.execute(
            "UPDATE public.payment_links SET status = $1 WHERE id = $2",
            status, link["id"],
        )
    return {
        "invoice": await billing.get_invoice(conn, invoice_id),
        "link": await _get_link(conn, link["id"]),
    }


def _first_payment_id(link_entity: dict) -> str | None:
    payments = link_entity.get("payments") or []
    for p in payments:
        if p.get("status") == "captured":
            return p.get("payment_id") or p.get("id")
    return payments[0].get("payment_id") if payments else None


async def _reconcile_paid(
    conn: asyncpg.Connection, link: dict, provider_payment_id: str | None, actor_id: str | None
) -> None:
    """Record the payment for a paid link exactly once."""
    # Idempotency guard 1: link already marked paid.
    if link["status"] == "paid":
        return
    # Idempotency guard 2: this Razorpay payment id was already recorded.
    if provider_payment_id:
        existing = await conn.fetchval(
            "SELECT 1 FROM public.payments WHERE invoice_id = $1 AND reference = $2",
            link["invoice_id"], provider_payment_id,
        )
        if existing:
            await conn.execute(
                "UPDATE public.payment_links SET status = 'paid', "
                "provider_payment_id = $1, paid_at = COALESCE(paid_at, now()) "
                "WHERE id = $2",
                provider_payment_id, link["id"],
            )
            return

    inv = await conn.fetchrow(
        "SELECT status, grand_total, amount_paid FROM public.invoices WHERE id = $1",
        link["invoice_id"],
    )
    due = Decimal(inv["grand_total"]) - Decimal(inv["amount_paid"])
    # Never over-record: cap at the current amount due (cash may have been taken
    # since the link was created).
    to_record = min(Decimal(link["amount"]), due)

    payment_db_id = None
    if to_record > 0 and inv["status"] not in ("draft", "cancelled"):
        payment_db_id = await conn.fetchval(
            "INSERT INTO public.payments (invoice_id, amount, method, reference, "
            "received_by) VALUES ($1, $2, 'razorpay', $3, $4::uuid) RETURNING id",
            link["invoice_id"], to_record, provider_payment_id, actor_id,
        )
        await billing._recompute(conn, link["invoice_id"])

    await conn.execute(
        "UPDATE public.payment_links SET status = 'paid', provider_payment_id = $1, "
        "payment_id = $2, paid_at = now() WHERE id = $3",
        provider_payment_id, payment_db_id, link["id"],
    )
    await write_audit(conn, actor_id=actor_id, action="payment",
                      entity="invoices", entity_id=link["invoice_id"],
                      detail={"amount": str(to_record), "method": "razorpay",
                              "razorpay_payment_id": provider_payment_id})


async def handle_webhook_event(conn: asyncpg.Connection, event: dict) -> None:
    """Process a verified Razorpay webhook event."""
    if event.get("event") != "payment_link.paid":
        return  # only settlement events matter to us
    payload = event.get("payload", {})
    link_entity = payload.get("payment_link", {}).get("entity", {})
    payment_entity = payload.get("payment", {}).get("entity", {})
    provider_link_id = link_entity.get("id")
    provider_payment_id = payment_entity.get("id")
    if not provider_link_id:
        return

    link = await conn.fetchrow(
        "SELECT id, invoice_id, amount, status FROM public.payment_links "
        "WHERE provider_link_id = $1",
        provider_link_id,
    )
    if link is None:
        return  # unknown link — nothing to reconcile
    # Webhook has no logged-in user; record the payment with a null actor.
    await _reconcile_paid(conn, dict(link), provider_payment_id, None)
