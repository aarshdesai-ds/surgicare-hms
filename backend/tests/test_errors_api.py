"""HTTP-layer error-envelope + RBAC tests via TestClient (no DB needed).

These exercise auth and request validation, which run before the handler
touches the database.
"""

from __future__ import annotations

import time

from jose import jwt

from app.config import settings


def _token(role: str) -> str:
    claims = {
        "sub": "tester", "aud": "authenticated",
        "exp": int(time.time()) + 3600, "app_metadata": {"role": role},
    }
    return jwt.encode(claims, settings.supabase_jwt_secret, algorithm="HS256")


def _auth(role: str) -> dict:
    return {"Authorization": f"Bearer {_token(role)}"}


def test_create_patient_requires_auth(client):
    r = client.post("/api/patients", json={"first_name": "A", "phone": "9876543210"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_create_patient_forbidden_for_wrong_role(client):
    # billing role may not create patients (reception/admin only) -> 403
    r = client.post(
        "/api/patients", headers=_auth("billing"),
        json={"first_name": "A", "phone": "9876543210"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_create_patient_validation_envelope(client):
    # admin passes RBAC; invalid body -> 400 with field details
    r = client.post(
        "/api/patients", headers=_auth("admin"),
        json={"last_name": "OnlyLast", "phone": "12345"},  # missing first_name, bad phone
    )
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "fields" in body["error"]
    # at least one of the bad fields is reported
    assert any(k in body["error"]["fields"] for k in ("first_name", "phone"))


def test_unknown_route_404_envelope(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_queue_status_validation(client):
    # invalid status value -> 400 validation envelope (admin passes RBAC)
    r = client.patch(
        "/api/queue/1/status", headers=_auth("admin"), json={"status": "teleported"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
