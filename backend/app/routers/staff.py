"""Staff / roles management endpoints (admin only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import CurrentUser, require_roles
from ..database import require_pool
from ..schemas.staff import StaffCreate, StaffUpdate
from ..services import staff as service

router = APIRouter(prefix="/api", tags=["staff"])

_ADMIN = require_roles("admin")


@router.get("/staff")
async def list_staff(_: CurrentUser = Depends(_ADMIN)) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return {"items": await service.list_staff(conn)}


@router.post("/staff", status_code=201)
async def create_staff(
    payload: StaffCreate, user: CurrentUser = Depends(_ADMIN)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.create_staff(conn, payload, user.id)


@router.patch("/staff/{staff_id}")
async def update_staff(
    staff_id: str, payload: StaffUpdate, user: CurrentUser = Depends(_ADMIN)
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await service.update_staff(conn, staff_id, payload, user.id)
