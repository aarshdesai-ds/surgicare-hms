"""End-of-day report endpoint."""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, Query

from ..auth import CurrentUser, get_current_user
from ..database import require_pool
from ..services import reports as service

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/reports/day")
async def day_report(
    day: date_type = Query(...),
    _: CurrentUser = Depends(get_current_user),
) -> dict:
    pool = require_pool()
    async with pool.acquire() as conn:
        return await service.day_report(conn, day)
