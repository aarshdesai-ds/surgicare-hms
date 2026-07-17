"""Billing business logic: catalog, invoices, line items, payments.

All money math is done here (server-side); the client never sends totals.
Draft invoices are editable; finalizing assigns a number and locks line items.
"""

from __future__ import annotations

from decimal import Decimal

import asyncpg

from ..errors import AppError
from ..schemas.billing import (
    DiscountUpdate, InvoiceCreate, LineItemCreate, PaymentCreate,
    ServiceCreate, ServiceUpdate,
)
from ..utils.audit import write_audit


# ------------------------- catalog -------------------------
async def list_services(conn: asyncpg.Connection, active_only: bool) -> list[dict]:
    where = "WHERE is_active = true" if active_only else ""
    rows = await conn.fetch(
        f"SELECT id, code, name, category, unit_price, gst_rate, is_active "
        f"FROM public.service_catalog {where} ORDER BY category, name"
    )
    return [dict(r) for r in rows]


async def create_service(
    conn: asyncpg.Connection, data: ServiceCreate, actor_id: str
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO public.service_catalog
            (code, name, category, unit_price, gst_rate, is_active)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, code, name, category, unit_price, gst_rate, is_active
        """,
        data.code, data.name, data.category, data.unit_price,
        data.gst_rate, data.is_active,
    )
    await write_audit(conn, actor_id=actor_id, action="create",
                      entity="service_catalog", entity_id=row["id"])
    return dict(row)


async def update_service(
    conn: asyncpg.Connection, service_id: int, data: ServiceUpdate, actor_id: str
) -> dict:
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        raise AppError("VALIDATION_ERROR", "Nothing to update.", status_code=400)
    sets, params = [], []
    for col, val in fields.items():
        params.append(val)
        sets.append(f"{col} = ${len(params)}")
    params.append(service_id)
    row = await conn.fetchrow(
        f"UPDATE public.service_catalog SET {', '.join(sets)} "
        f"WHERE id = ${len(params)} "
        f"RETURNING id, code, name, category, unit_price, gst_rate, is_active",
        *params,
    )
    if row is None:
        raise AppError("NOT_FOUND", "Service not found.", status_code=404)
    await write_audit(conn, actor_id=actor_id, action="update",
                      entity="service_catalog", entity_id=service_id)
    return dict(row)


# ------------------------- invoices -------------------------
_INVOICE_SELECT = """
    SELECT i.id, i.invoice_no, i.patient_id, i.status, i.subtotal, i.tax_total,
           i.discount, i.grand_total, i.amount_paid, i.notes, i.created_at,
           i.finalized_at,
           p.uhid AS patient_uhid,
           (p.first_name || ' ' || COALESCE(p.last_name, '')) AS patient_name,
           p.phone AS patient_phone
    FROM public.invoices i
    JOIN public.patients p ON p.id = i.patient_id
"""


async def _recompute(conn: asyncpg.Connection, invoice_id: int) -> None:
    """Recalculate invoice totals from its line items + payments."""
    agg = await conn.fetchrow(
        """
        SELECT COALESCE(SUM(line_total), 0) AS subtotal,
               COALESCE(SUM(line_total * gst_rate / 100), 0) AS tax_total
        FROM public.invoice_line_items WHERE invoice_id = $1
        """,
        invoice_id,
    )
    paid = await conn.fetchval(
        "SELECT COALESCE(SUM(amount), 0) FROM public.payments WHERE invoice_id = $1",
        invoice_id,
    )
    inv = await conn.fetchrow(
        "SELECT discount, status FROM public.invoices WHERE id = $1", invoice_id
    )
    subtotal = Decimal(agg["subtotal"])
    tax_total = Decimal(agg["tax_total"]).quantize(Decimal("0.01"))
    discount = Decimal(inv["discount"])
    grand = subtotal + tax_total - discount
    if grand < 0:
        grand = Decimal("0")
    paid = Decimal(paid)

    status = inv["status"]
    if status in ("finalized", "partially_paid", "paid"):
        if paid >= grand and grand > 0:
            status = "paid"
        elif paid > 0:
            status = "partially_paid"
        else:
            status = "finalized"

    await conn.execute(
        """
        UPDATE public.invoices
        SET subtotal = $1, tax_total = $2, grand_total = $3,
            amount_paid = $4, status = $5
        WHERE id = $6
        """,
        subtotal, tax_total, grand, paid, status, invoice_id,
    )


async def get_invoice(conn: asyncpg.Connection, invoice_id: int) -> dict:
    inv = await conn.fetchrow(f"{_INVOICE_SELECT} WHERE i.id = $1", invoice_id)
    if inv is None:
        raise AppError("NOT_FOUND", "Invoice not found.", status_code=404)
    items = await conn.fetch(
        "SELECT id, service_id, description, source, quantity, unit_price, "
        "gst_rate, line_total FROM public.invoice_line_items "
        "WHERE invoice_id = $1 ORDER BY id",
        invoice_id,
    )
    payments = await conn.fetch(
        "SELECT id, amount, method, reference, received_at "
        "FROM public.payments WHERE invoice_id = $1 ORDER BY received_at",
        invoice_id,
    )
    result = dict(inv)
    result["line_items"] = [dict(r) for r in items]
    result["payments"] = [dict(r) for r in payments]
    return result


async def list_invoices(
    conn: asyncpg.Connection, patient_id: int | None, limit: int, offset: int
) -> tuple[list[dict], int]:
    limit = max(1, min(limit, 100))
    params: list = []
    where = ""
    if patient_id is not None:
        params.append(patient_id)
        where = "WHERE i.patient_id = $1"
    total = await conn.fetchval(
        f"SELECT COUNT(*) FROM public.invoices i {where}", *params
    )
    rows = await conn.fetch(
        f"{_INVOICE_SELECT} {where} ORDER BY i.created_at DESC "
        f"LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}",
        *params, limit, offset,
    )
    return [dict(r) for r in rows], int(total)


async def create_invoice(
    conn: asyncpg.Connection, data: InvoiceCreate, actor_id: str
) -> dict:
    if not await conn.fetchval(
        "SELECT 1 FROM public.patients WHERE id = $1", data.patient_id
    ):
        raise AppError("NOT_FOUND", "Patient not found.", status_code=404)
    row = await conn.fetchrow(
        "INSERT INTO public.invoices (patient_id, notes, created_by) "
        "VALUES ($1, $2, $3::uuid) RETURNING id",
        data.patient_id, data.notes, actor_id,
    )
    await write_audit(conn, actor_id=actor_id, action="create",
                      entity="invoices", entity_id=row["id"])
    return await get_invoice(conn, row["id"])


async def _require_draft(conn: asyncpg.Connection, invoice_id: int) -> None:
    status = await conn.fetchval(
        "SELECT status FROM public.invoices WHERE id = $1", invoice_id
    )
    if status is None:
        raise AppError("NOT_FOUND", "Invoice not found.", status_code=404)
    if status != "draft":
        raise AppError(
            "INVOICE_LOCKED",
            "This invoice is finalized and can no longer be edited.",
            status_code=422,
        )


async def add_line_item(
    conn: asyncpg.Connection, invoice_id: int, data: LineItemCreate, actor_id: str
) -> dict:
    await _require_draft(conn, invoice_id)
    line_total = (data.quantity * data.unit_price).quantize(Decimal("0.01"))
    await conn.execute(
        """
        INSERT INTO public.invoice_line_items
            (invoice_id, service_id, description, source, quantity,
             unit_price, gst_rate, line_total)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        invoice_id, data.service_id, data.description, data.source,
        data.quantity, data.unit_price, data.gst_rate, line_total,
    )
    await _recompute(conn, invoice_id)
    return await get_invoice(conn, invoice_id)


async def remove_line_item(
    conn: asyncpg.Connection, invoice_id: int, item_id: int, actor_id: str
) -> dict:
    await _require_draft(conn, invoice_id)
    await conn.execute(
        "DELETE FROM public.invoice_line_items WHERE id = $1 AND invoice_id = $2",
        item_id, invoice_id,
    )
    await _recompute(conn, invoice_id)
    return await get_invoice(conn, invoice_id)


async def set_discount(
    conn: asyncpg.Connection, invoice_id: int, data: DiscountUpdate, actor_id: str
) -> dict:
    await _require_draft(conn, invoice_id)
    await conn.execute(
        "UPDATE public.invoices SET discount = $1 WHERE id = $2",
        data.discount, invoice_id,
    )
    await _recompute(conn, invoice_id)
    return await get_invoice(conn, invoice_id)


async def finalize_invoice(
    conn: asyncpg.Connection, invoice_id: int, actor_id: str
) -> dict:
    status = await conn.fetchval(
        "SELECT status FROM public.invoices WHERE id = $1", invoice_id
    )
    if status is None:
        raise AppError("NOT_FOUND", "Invoice not found.", status_code=404)
    if status != "draft":
        raise AppError("ALREADY_FINALIZED", "Invoice is already finalized.",
                       status_code=422)
    has_items = await conn.fetchval(
        "SELECT 1 FROM public.invoice_line_items WHERE invoice_id = $1", invoice_id
    )
    if not has_items:
        raise AppError("EMPTY_INVOICE", "Add at least one item before finalizing.",
                       status_code=422)

    invoice_no = await conn.fetchval(
        "SELECT 'INV-' || to_char(now(), 'YYYY') || '-' || "
        "lpad(nextval('public.invoice_no_seq')::text, 6, '0')"
    )
    await conn.execute(
        "UPDATE public.invoices SET status = 'finalized', invoice_no = $1, "
        "finalized_at = now() WHERE id = $2",
        invoice_no, invoice_id,
    )
    await _recompute(conn, invoice_id)
    await write_audit(conn, actor_id=actor_id, action="finalize",
                      entity="invoices", entity_id=invoice_id,
                      detail={"invoice_no": invoice_no})
    return await get_invoice(conn, invoice_id)


async def cancel_invoice(
    conn: asyncpg.Connection, invoice_id: int, actor_id: str
) -> dict:
    status = await conn.fetchval(
        "SELECT status FROM public.invoices WHERE id = $1", invoice_id
    )
    if status is None:
        raise AppError("NOT_FOUND", "Invoice not found.", status_code=404)
    if status == "paid":
        raise AppError("CANNOT_CANCEL", "A paid invoice cannot be cancelled.",
                       status_code=422)
    await conn.execute(
        "UPDATE public.invoices SET status = 'cancelled' WHERE id = $1", invoice_id
    )
    await write_audit(conn, actor_id=actor_id, action="cancel",
                      entity="invoices", entity_id=invoice_id)
    return await get_invoice(conn, invoice_id)


async def add_payment(
    conn: asyncpg.Connection, invoice_id: int, data: PaymentCreate, actor_id: str
) -> dict:
    inv = await conn.fetchrow(
        "SELECT status, grand_total, amount_paid FROM public.invoices WHERE id = $1",
        invoice_id,
    )
    if inv is None:
        raise AppError("NOT_FOUND", "Invoice not found.", status_code=404)
    if inv["status"] in ("draft", "cancelled"):
        raise AppError(
            "NOT_PAYABLE",
            "Finalize the invoice before recording a payment.",
            status_code=422,
        )
    due = Decimal(inv["grand_total"]) - Decimal(inv["amount_paid"])
    if data.amount > due:
        raise AppError(
            "OVERPAYMENT",
            f"Payment exceeds the amount due ({due}).",
            status_code=422,
            fields={"due": str(due)},
        )
    await conn.execute(
        "INSERT INTO public.payments (invoice_id, amount, method, reference, "
        "received_by) VALUES ($1, $2, $3, $4, $5::uuid)",
        invoice_id, data.amount, data.method, data.reference, actor_id,
    )
    await _recompute(conn, invoice_id)
    await write_audit(conn, actor_id=actor_id, action="payment",
                      entity="invoices", entity_id=invoice_id,
                      detail={"amount": str(data.amount), "method": data.method})
    return await get_invoice(conn, invoice_id)
