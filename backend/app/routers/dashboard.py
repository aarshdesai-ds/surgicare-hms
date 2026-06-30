"""Dashboard summary endpoint."""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, get_current_user
from ..database import require_pool
from ..services import dashboard as service

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
async def dashboard_summary(
    day: date_type = Query(...),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return await service.summary(conn, day)
