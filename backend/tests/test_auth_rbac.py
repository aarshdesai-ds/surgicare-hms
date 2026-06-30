"""Auth + role-based access control unit tests (no DB).

Covers test-plan cases 5 (invalid token) and 6 (role gating) at the unit level,
plus the typo-guard on require_roles.
"""

from __future__ import annotations

import time

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.auth import CurrentUser, get_current_user, require_roles
from app.config import settings
from app.errors import AppError


def _token(role=None, sub="u1") -> str:
    claims = {"sub": sub, "aud": "authenticated", "exp": int(time.time()) + 3600}
    if role is not None:
        claims["app_metadata"] = {"role": role}
    return jwt.encode(claims, settings.supabase_jwt_secret, algorithm="HS256")


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


async def test_missing_credentials_401():
    with pytest.raises(AppError) as exc:
        await get_current_user(None)
    assert exc.value.status_code == 401


async def test_garbage_token_401():
    with pytest.raises(AppError) as exc:
        await get_current_user(_creds("not-a-jwt"))
    assert exc.value.status_code == 401


async def test_expired_token_401():
    claims = {"sub": "u1", "aud": "authenticated", "exp": int(time.time()) - 10}
    token = jwt.encode(claims, settings.supabase_jwt_secret, algorithm="HS256")
    with pytest.raises(AppError) as exc:
        await get_current_user(_creds(token))
    assert exc.value.status_code == 401


async def test_role_read_from_jwt():
    user = await get_current_user(_creds(_token(role="billing")))
    assert user.id == "u1"
    assert user.role == "billing"


async def test_require_roles_allows_matching():
    dep = require_roles("admin", "reception")
    user = await dep(user=CurrentUser(id="x", role="reception"))
    assert user.role == "reception"


async def test_require_roles_forbids_other():
    dep = require_roles("admin", "reception")
    with pytest.raises(AppError) as exc:
        await dep(user=CurrentUser(id="x", role="doctor"))
    assert exc.value.status_code == 403


def test_require_roles_rejects_unknown_role():
    # Guards against typos like require_roles("suregon") at import time.
    with pytest.raises(ValueError):
        require_roles("suregon")
