"""Prescription + pharmacy outbox endpoints.

Two audiences:
  * Staff (Supabase JWT) — create prescriptions, view them, manually mark sent.
  * The offline pharmacy bridge agent — a headless process on the pharmacy PC
    that pulls pending prescriptions and marks them delivered. It authenticates
    with a single shared token (X-Bridge-Token), scoped to just these two
    endpoints, so the pharmacy machine never stores a full staff login.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, Query

from ..auth import CurrentUser, get_current_user, require_roles
from ..config import settings
from ..database import require_pool
from ..errors import AppError
from ..schemas.prescription import PrescriptionCreate
from ..services import pharmacy as service

router = APIRouter(prefix="/api", tags=["pharmacy"])

_WRITERS = require_roles("reception", "admin", "doctor", "nurse")


async def bridge_auth(x_bridge_token: str | None = Header(default=None)) -> None:
    """Gate the bridge endpoints on the shared token (constant-time compare)."""
    token = settings.pharmacy_bridge_token
    if not token or not x_bridge_token or not hmac.compare_digest(x_bridge_token, token):
        raise AppError("UNAUTHORIZED", "Invalid or missing bridge token.",
                       status_code=401)


@router.post("/prescriptions", status_code=201)
async def create_prescription(
    payload: PrescriptionCreate, user: CurrentUser = Depends(_WRITERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.create(conn, payload, user.id)


@router.get("/prescriptions")
async def list_prescriptions(
    patient_id: int = Query(...),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return {"items": await service.list_for_patient(conn, patient_id)}


@router.get("/prescriptions/{rx_id}")
async def get_prescription(
    rx_id: int, _: CurrentUser = Depends(get_current_user)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return await service.get_by_id(conn, rx_id)


@router.get("/pharmacy/outbox")
async def list_outbox(
    status: str = Query("pending"),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return {"items": await service.list_outbox(conn, status)}


@router.post("/pharmacy/outbox/{outbox_id}/sent")
async def mark_sent(
    outbox_id: int, user: CurrentUser = Depends(_WRITERS)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.mark_sent(conn, outbox_id, user.id)


# ---- bridge agent (token-authenticated, scoped to the pharmacy outbox) ----
@router.get("/pharmacy/bridge/pending")
async def bridge_pending(_: None = Depends(bridge_auth)) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return {"items": await service.list_outbox(conn, "pending")}


@router.post("/pharmacy/bridge/sent/{outbox_id}")
async def bridge_mark_sent(
    outbox_id: int, _: None = Depends(bridge_auth)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # No staff user for a headless agent — audited with a null actor.
            return await service.mark_sent(conn, outbox_id, None)
