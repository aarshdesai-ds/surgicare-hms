"""Health and readiness endpoints, plus a `/me` route to verify auth wiring."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import __version__
from ..auth import CurrentUser, get_current_user
from ..database import ping

router = APIRouter(tags=["system"])


@router.get("/healthz")
async def healthz() -> dict:
    """Liveness: always 200 if the process is up. Reports DB connectivity."""
    db_ok = await ping()
    return {
        "status": "ok",
        "version": __version__,
        "database": "up" if db_ok else "down",
    }


@router.get("/readyz")
async def readyz() -> dict:
    """Readiness: 200 only when dependencies (DB) are reachable."""
    db_ok = await ping()
    if not db_ok:
        from ..errors import AppError

        raise AppError(
            code="NOT_READY",
            message="Database is not reachable.",
            status_code=503,
        )
    return {"status": "ready"}


@router.get("/api/me")
async def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    """Echo the authenticated user — confirms JWT verification works end-to-end."""
    return {"id": user.id, "email": user.email, "role": user.role}
