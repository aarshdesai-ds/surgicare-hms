"""Billing endpoints: service catalog, invoices, line items, payments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, get_current_user, require_roles
from ..database import require_pool
from ..schemas.billing import (
    DiscountUpdate, InvoiceCreate, LineItemCreate, PaymentCreate,
    ServiceCreate, ServiceUpdate,
)
from ..services import billing as service

router = APIRouter(prefix="/api", tags=["billing"])

_BILLERS = require_roles("billing", "admin", "reception")
_CATALOG_ADMIN = require_roles("billing", "admin")


# ---- service catalog ----
@router.get("/services")
async def list_services(
    active_only: bool = Query(False),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return {"items": await service.list_services(conn, active_only)}


@router.post("/services", status_code=201)
async def create_service(
    payload: ServiceCreate, user: CurrentUser = Depends(_CATALOG_ADMIN)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.create_service(conn, payload, user.id)


@router.patch("/services/{service_id}")
async def update_service(
    service_id: int, payload: ServiceUpdate,
    user: CurrentUser = Depends(_CATALOG_ADMIN),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.update_service(conn, service_id, payload, user.id)


# ---- invoices ----
@router.get("/invoices")
async def list_invoices(
    patient_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        items, total = await service.list_invoices(conn, patient_id, limit, offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/invoices", status_code=201)
async def create_invoice(
    payload: InvoiceCreate, user: CurrentUser = Depends(_BILLERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.create_invoice(conn, payload, user.id)


@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: int, _: CurrentUser = Depends(get_current_user)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return await service.get_invoice(conn, invoice_id)


@router.post("/invoices/{invoice_id}/items")
async def add_item(
    invoice_id: int, payload: LineItemCreate, user: CurrentUser = Depends(_BILLERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.add_line_item(conn, invoice_id, payload, user.id)


@router.delete("/invoices/{invoice_id}/items/{item_id}")
async def remove_item(
    invoice_id: int, item_id: int, user: CurrentUser = Depends(_BILLERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.remove_line_item(conn, invoice_id, item_id, user.id)


@router.patch("/invoices/{invoice_id}/discount")
async def set_discount(
    invoice_id: int, payload: DiscountUpdate, user: CurrentUser = Depends(_BILLERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.set_discount(conn, invoice_id, payload, user.id)


@router.post("/invoices/{invoice_id}/finalize")
async def finalize(
    invoice_id: int, user: CurrentUser = Depends(_BILLERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.finalize_invoice(conn, invoice_id, user.id)


@router.post("/invoices/{invoice_id}/cancel")
async def cancel(
    invoice_id: int, user: CurrentUser = Depends(_BILLERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.cancel_invoice(conn, invoice_id, user.id)


@router.post("/invoices/{invoice_id}/payments")
async def add_payment(
    invoice_id: int, payload: PaymentCreate, user: CurrentUser = Depends(_BILLERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.add_payment(conn, invoice_id, payload, user.id)
