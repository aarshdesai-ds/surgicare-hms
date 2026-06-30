"""Day 1 foundation tests: health, auth wiring, and the error envelope."""

from __future__ import annotations

import time

from jose import jwt

from app.config import settings


def _make_token(role: str | None = "reception", sub: str = "user-123") -> str:
    claims = {
        "sub": sub,
        "email": "staff@example.com",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "app_metadata": {"role": role} if role else {},
    }
    return jwt.encode(claims, settings.supabase_jwt_secret, algorithm="HS256")


def test_healthz_is_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # No DB configured in tests → reported as down, but the endpoint still 200s.
    assert body["database"] in ("up", "down")


def test_me_requires_auth(client):
    resp = client.get("/api/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_me_returns_user_with_valid_token(client):
    token = _make_token(role="billing")
    resp = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "user-123"
    assert body["role"] == "billing"


def test_me_rejects_garbage_token(client):
    resp = client.get("/api/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_error_envelope_shape_on_404(client):
    resp = client.get("/does-not-exist")
    assert resp.status_code == 404
    assert "error" in resp.json()
    assert resp.json()["error"]["code"] == "NOT_FOUND"
