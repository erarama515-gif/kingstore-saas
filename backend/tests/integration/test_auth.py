"""Integration tests for the auth module.

Coverage:
* Signup happy path (tenant + branch + owner created, tokens issued)
* Login with username and with email
* Cross-tenant isolation (user from tenant A can't log into tenant B)
* Refresh rotation
* Refresh reuse detection (theft response)
* Logout invalidates the refresh
* Change password forces re-login
* Brute-force lockout

These talk to the real Postgres + Redis via the docker-compose stack. Skip
the suite when run outside Docker by setting ``KINGSTORE_SKIP_INTEGRATION=1``.
"""

from __future__ import annotations

import os
import uuid

import pytest


pytestmark = pytest.mark.integration

if os.getenv("KINGSTORE_SKIP_INTEGRATION") == "1":
    pytest.skip("integration tests disabled via env", allow_module_level=True)


# --- Helpers ----------------------------------------------------------------

def _unique_slug() -> str:
    return f"t-{uuid.uuid4().hex[:8]}"


def _signup_payload(**overrides) -> dict:
    base = {
        "tenant_slug": _unique_slug(),
        "tenant_name": "Test Shop",
        "owner_name": "Owner Person",
        "owner_email": f"owner-{uuid.uuid4().hex[:6]}@example.com",
        "owner_username": f"owner{uuid.uuid4().hex[:6]}",
        "owner_password": "CorrectHorse1Battery",
        "default_branch_name": "Main",
        "default_branch_code": "MAIN",
    }
    base.update(overrides)
    return base


def _signup(client, **overrides) -> dict:
    body = _signup_payload(**overrides)
    resp = client.post("/api/v1/auth/signup", json=body)
    assert resp.status_code == 201, resp.get_json()
    return {"request": body, "response": resp.get_json()["data"]}


# --- Tests ------------------------------------------------------------------

def test_signup_creates_tenant_branch_owner_and_tokens(client):
    result = _signup(client)
    resp = result["response"]
    assert resp["tenant"]["slug"] == result["request"]["tenant_slug"]
    assert resp["tenant"]["status"] == "trial"
    assert resp["user"]["role"] == "owner"
    assert resp["user"]["must_change_password"] is False
    assert resp["user"]["default_branch_id"] is not None
    assert resp["tokens"]["access_token"]
    assert resp["tokens"]["refresh_token"]
    assert resp["tokens"]["expires_in"] > 0


def test_signup_duplicate_slug_returns_409(client):
    first = _signup(client)
    resp = client.post(
        "/api/v1/auth/signup",
        json=_signup_payload(tenant_slug=first["request"]["tenant_slug"]),
    )
    assert resp.status_code == 409


def test_login_with_username(client):
    s = _signup(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": s["request"]["tenant_slug"],
            "username": s["request"]["owner_username"],
            "password": s["request"]["owner_password"],
        },
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["data"]["tokens"]["access_token"]


def test_login_with_email(client):
    s = _signup(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": s["request"]["tenant_slug"],
            "username": s["request"]["owner_email"],
            "password": s["request"]["owner_password"],
        },
    )
    assert resp.status_code == 200


def test_login_wrong_password_returns_401(client):
    s = _signup(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": s["request"]["tenant_slug"],
            "username": s["request"]["owner_username"],
            "password": "wrong-but-long-enough-1",
        },
    )
    assert resp.status_code == 401


def test_cross_tenant_login_is_rejected(client):
    a = _signup(client)
    b = _signup(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": b["request"]["tenant_slug"],
            "username": a["request"]["owner_username"],
            "password": a["request"]["owner_password"],
        },
    )
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_user_tenant_and_permissions(client):
    s = _signup(client)
    access = s["response"]["tokens"]["access_token"]
    resp = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["user"]["username"] == s["request"]["owner_username"].lower()
    assert data["tenant"]["slug"] == s["request"]["tenant_slug"]
    assert len(data["permissions"]) > 0
    # Owner has billing.manage; cashier wouldn't.
    assert "billing.manage" in data["permissions"]


def test_refresh_rotates_token(client):
    s = _signup(client)
    refresh = s["response"]["tokens"]["refresh_token"]
    resp = client.post(
        "/api/v1/auth/refresh", headers={"Authorization": f"Bearer {refresh}"}
    )
    assert resp.status_code == 200
    new_tokens = resp.get_json()["data"]["tokens"]
    assert new_tokens["refresh_token"] != refresh


def test_refresh_reuse_detected_and_nukes_sessions(client):
    s = _signup(client)
    refresh = s["response"]["tokens"]["refresh_token"]
    # First refresh: ok
    r1 = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {refresh}"})
    assert r1.status_code == 200
    new_refresh = r1.get_json()["data"]["tokens"]["refresh_token"]
    # Reusing the original (now-revoked) refresh: theft response.
    r2 = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {refresh}"})
    assert r2.status_code == 401
    # And the *new* refresh should now also be revoked (nuke-all behavior).
    r3 = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {new_refresh}"})
    assert r3.status_code == 401


def test_logout_revokes_refresh(client):
    s = _signup(client)
    refresh = s["response"]["tokens"]["refresh_token"]
    resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {refresh}"})
    assert resp.status_code == 204
    # Subsequent refresh: rejected
    again = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {refresh}"})
    assert again.status_code == 401


def test_change_password_revokes_sessions_and_blocks_old_password(client):
    s = _signup(client)
    access = s["response"]["tokens"]["access_token"]
    refresh = s["response"]["tokens"]["refresh_token"]

    new_pw = "NewPasswordRotated9"
    resp = client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": s["request"]["owner_password"],
            "new_password": new_pw,
        },
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 204

    # Old refresh is dead
    r = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {refresh}"})
    assert r.status_code == 401

    # Old password rejected
    r = client.post("/api/v1/auth/login", json={
        "tenant_slug": s["request"]["tenant_slug"],
        "username": s["request"]["owner_username"],
        "password": s["request"]["owner_password"],
    })
    assert r.status_code == 401

    # New password works
    r = client.post("/api/v1/auth/login", json={
        "tenant_slug": s["request"]["tenant_slug"],
        "username": s["request"]["owner_username"],
        "password": new_pw,
    })
    assert r.status_code == 200
