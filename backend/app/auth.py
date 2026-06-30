"""Supabase JWT verification and role-based access control.

The React app authenticates with Supabase Auth and receives a JWT, sent as
`Authorization: Bearer <token>`. We verify it here. Supabase signs tokens with
EITHER:
  * the legacy shared secret (HS256), or
  * an asymmetric signing key (RS256/ES256) exposed via the project's JWKS.
This module supports both: it inspects the token header and verifies
accordingly, fetching+caching the JWKS for asymmetric tokens.

Role convention: set the user's role in Supabase under `app_metadata.role`
(e.g. via the Auth admin API or a SQL trigger). Valid roles:
admin, doctor, reception, billing, nurse.
"""

from __future__ import annotations

import time
from typing import Callable

import httpx
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from .config import settings
from .errors import AppError
from .logging_config import get_logger

log = get_logger(__name__)

VALID_ROLES = {"admin", "doctor", "reception", "billing", "nurse"}

_bearer = HTTPBearer(auto_error=False)

# --- JWKS cache (for asymmetric tokens) -------------------------------------
_JWKS_TTL_SECONDS = 600
_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}


async def _get_jwks(force: bool = False) -> list[dict]:
    now = time.time()
    if (
        not force
        and _jwks_cache["keys"] is not None
        and now - _jwks_cache["fetched_at"] < _JWKS_TTL_SECONDS
    ):
        return _jwks_cache["keys"]

    url = settings.supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        keys = resp.json().get("keys", [])

    _jwks_cache["keys"] = keys
    _jwks_cache["fetched_at"] = now
    return keys


async def _verify_token(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    alg = header.get("alg")

    if alg == "HS256":
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )

    # Asymmetric (RS256 / ES256): verify against the project's public JWKS.
    kid = header.get("kid")
    keys = await _get_jwks()
    key = next((k for k in keys if k.get("kid") == kid), None)
    if key is None:
        # Key may have rotated; refresh once and retry.
        keys = await _get_jwks(force=True)
        key = next((k for k in keys if k.get("kid") == kid), None)
    if key is None:
        raise JWTError(f"No matching JWKS key for kid={kid}")

    return jwt.decode(
        token,
        key,
        algorithms=[alg],
        audience="authenticated",
    )


class CurrentUser(BaseModel):
    id: str
    email: str | None = None
    role: str | None = None


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """Verify the bearer token and return the authenticated user."""
    if creds is None or not creds.credentials:
        raise AppError(
            code="UNAUTHENTICATED",
            message="Missing or malformed Authorization header.",
            status_code=401,
        )
    try:
        payload = await _verify_token(creds.credentials)
    except (JWTError, httpx.HTTPError) as exc:
        # Log the real reason server-side; never leak it to the client.
        log.warning("auth.token_invalid", error=str(exc))
        raise AppError(
            code="UNAUTHENTICATED",
            message="Invalid or expired token.",
            status_code=401,
        ) from exc

    user_id = payload.get("sub", "")

    # Role source of truth is the profiles table. Prefer an explicit role in the
    # JWT (if a Supabase auth hook injects one later) and fall back to a DB lookup.
    app_metadata = payload.get("app_metadata") or {}
    role = app_metadata.get("role")
    if role is None and user_id:
        role = await _lookup_role(user_id)

    return CurrentUser(
        id=user_id,
        email=payload.get("email"),
        role=role,
    )


async def _lookup_role(user_id: str) -> str | None:
    """Read the user's role from public.profiles. Returns None if unavailable."""
    from .database import db

    if db.pool is None:
        return None
    try:
        async with db.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT role FROM public.profiles "
                "WHERE id = $1::uuid AND is_active = true",
                user_id,
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("auth.role_lookup_failed", error=str(exc))
        return None


def require_roles(*roles: str) -> Callable:
    """Dependency factory: allow only the given roles.

    Usage:
        @router.post("/patients",
                     dependencies=[Depends(require_roles("reception", "admin"))])
    """
    allowed = set(roles)
    unknown = allowed - VALID_ROLES
    if unknown:  # guard against typos at import time
        raise ValueError(f"Unknown role(s) in require_roles: {unknown}")

    async def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise AppError(
                code="FORBIDDEN",
                message="You do not have permission to perform this action.",
                status_code=403,
            )
        return user

    return _dep
