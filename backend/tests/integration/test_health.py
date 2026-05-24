"""Smoke test for /api/v1/health.

Proves the app boots, the blueprint is registered, and the JSON envelope
matches the contract.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_health_returns_ok(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "data" in body
    assert body["data"]["status"] == "ok"
    assert body["data"]["service"]
    assert body["data"]["version"]


@pytest.mark.integration
def test_security_headers_are_set(client):
    resp = client.get("/api/v1/health")
    # A representative sample — full coverage lives in a dedicated test later.
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in resp.headers
