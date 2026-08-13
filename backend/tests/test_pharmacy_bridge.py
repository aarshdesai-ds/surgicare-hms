"""Tests for the pharmacy bridge token auth + endpoints."""

from __future__ import annotations

import pytest

from app.config import settings
from app.errors import AppError
from app.routers.prescriptions import bridge_auth


@pytest.mark.asyncio
async def test_bridge_auth_accepts_matching_token(monkeypatch):
    monkeypatch.setattr(settings, "pharmacy_bridge_token", "s3cret-token")
    # Should not raise.
    assert await bridge_auth(x_bridge_token="s3cret-token") is None


@pytest.mark.asyncio
async def test_bridge_auth_rejects_wrong_token(monkeypatch):
    monkeypatch.setattr(settings, "pharmacy_bridge_token", "s3cret-token")
    with pytest.raises(AppError) as ei:
        await bridge_auth(x_bridge_token="nope")
    assert ei.value.status_code == 401


@pytest.mark.asyncio
async def test_bridge_auth_rejects_missing_token(monkeypatch):
    monkeypatch.setattr(settings, "pharmacy_bridge_token", "s3cret-token")
    with pytest.raises(AppError) as ei:
        await bridge_auth(x_bridge_token=None)
    assert ei.value.status_code == 401


@pytest.mark.asyncio
async def test_bridge_auth_rejects_when_disabled(monkeypatch):
    # Blank server token → bridge is off; nothing authenticates.
    monkeypatch.setattr(settings, "pharmacy_bridge_token", "")
    with pytest.raises(AppError) as ei:
        await bridge_auth(x_bridge_token="")
    assert ei.value.status_code == 401


def test_bridge_pending_endpoint_401_without_token(client, monkeypatch):
    monkeypatch.setattr(settings, "pharmacy_bridge_token", "s3cret-token")
    resp = client.get("/api/pharmacy/bridge/pending")
    assert resp.status_code == 401
    resp2 = client.get("/api/pharmacy/bridge/pending",
                       headers={"X-Bridge-Token": "wrong"})
    assert resp2.status_code == 401
