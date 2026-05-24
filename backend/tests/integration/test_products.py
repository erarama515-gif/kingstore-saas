"""Products module integration tests.

Coverage:
* create with explicit code/barcode
* create auto-generates barcode when omitted
* duplicate code rejected (409)
* duplicate barcode rejected (409)
* list / search / category filter
* update modifies fields and respects uniqueness
* soft-delete removes from list but doesn't blow up references
* POS lookup priority: code → barcode → name (exact)
* tenant A cannot see / modify tenant B's products
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest


pytestmark = pytest.mark.integration

if os.getenv("KINGSTORE_SKIP_INTEGRATION") == "1":
    pytest.skip("integration tests disabled via env", allow_module_level=True)


# --- Helpers ----------------------------------------------------------------

def _signup(client) -> dict:
    payload = {
        "tenant_slug": f"t-{uuid.uuid4().hex[:8]}",
        "tenant_name": "Products Test Shop",
        "owner_name": "Owner",
        "owner_email": f"owner-{uuid.uuid4().hex[:6]}@example.com",
        "owner_username": f"owner{uuid.uuid4().hex[:6]}",
        "owner_password": "CorrectHorse1Battery",
        "default_branch_name": "Main",
        "default_branch_code": "MAIN",
    }
    resp = client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()["data"]
    return {
        "tenant_id": data["tenant"]["id"],
        "branch_id": data["user"]["default_branch_id"],
        "access": data["tokens"]["access_token"],
    }


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_product(client, headers, **overrides) -> dict:
    body = {
        "name": "iPhone 15",
        "category": "mobile",
        "code": None,
        "barcode": None,
        "cost": "20000.00",
        "price": "25000.00",
        "reorder_point": 2,
    }
    body.update(overrides)
    body = {k: v for k, v in body.items() if v is not None}
    r = client.post("/api/v1/products/", json=body, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["data"]


# --- Tests ------------------------------------------------------------------

def test_create_product_with_explicit_identifiers(client):
    s = _signup(client)
    h = _auth(s["access"])
    p = _create_product(client, h, code="MOB001", barcode="2123456789012")
    assert p["code"] == "MOB001"
    assert p["barcode"] == "2123456789012"
    assert Decimal(p["cost"]) == Decimal("20000.00")
    assert p["category"] == "mobile"
    assert p["is_active"] is True


def test_create_product_auto_generates_barcode(client):
    s = _signup(client)
    h = _auth(s["access"])
    p = _create_product(client, h)
    assert p["barcode"]
    assert p["barcode"].startswith("2")
    assert len(p["barcode"]) == 13
    # Two consecutive auto-barcodes should differ
    p2 = _create_product(client, h, name="iPhone 15 Pro")
    assert p2["barcode"] != p["barcode"]


def test_duplicate_code_rejected(client):
    s = _signup(client)
    h = _auth(s["access"])
    _create_product(client, h, code="ABC123")
    r = client.post(
        "/api/v1/products/",
        json={"name": "Other", "category": "mobile", "code": "ABC123", "price": "1"},
        headers=h,
    )
    assert r.status_code == 409


def test_duplicate_barcode_rejected(client):
    s = _signup(client)
    h = _auth(s["access"])
    _create_product(client, h, barcode="2000000000001")
    r = client.post(
        "/api/v1/products/",
        json={"name": "Other", "category": "mobile", "barcode": "2000000000001", "price": "1"},
        headers=h,
    )
    assert r.status_code == 409


def test_list_paginates_and_filters(client):
    s = _signup(client)
    h = _auth(s["access"])
    _create_product(client, h, name="Charger A", category="accessory")
    _create_product(client, h, name="Charger B", category="accessory")
    _create_product(client, h, name="Battery X", category="spare")

    r = client.get("/api/v1/products/?per_page=10", headers=h)
    assert r.status_code == 200
    data = r.get_json()
    assert len(data["data"]) == 3
    assert data["pagination"]["total"] == 3

    r2 = client.get("/api/v1/products/?category=accessory", headers=h)
    assert r2.status_code == 200
    assert len(r2.get_json()["data"]) == 2

    r3 = client.get("/api/v1/products/?q=Battery", headers=h)
    names = [p["name"] for p in r3.get_json()["data"]]
    assert names == ["Battery X"]


def test_update_fields(client):
    s = _signup(client)
    h = _auth(s["access"])
    p = _create_product(client, h, code="X1", price="100.00")
    r = client.patch(
        f"/api/v1/products/{p['id']}",
        json={"price": "150.50", "reorder_point": 5},
        headers=h,
    )
    assert r.status_code == 200, r.get_json()
    updated = r.get_json()["data"]
    assert Decimal(updated["price"]) == Decimal("150.50")
    assert updated["reorder_point"] == 5
    # untouched field stayed the same
    assert updated["code"] == "X1"


def test_update_to_duplicate_code_rejected(client):
    s = _signup(client)
    h = _auth(s["access"])
    _create_product(client, h, code="DUPE")
    other = _create_product(client, h, name="Other", code="UNQ")
    r = client.patch(
        f"/api/v1/products/{other['id']}",
        json={"code": "DUPE"},
        headers=h,
    )
    assert r.status_code == 409


def test_soft_delete_hides_from_list(client):
    s = _signup(client)
    h = _auth(s["access"])
    p = _create_product(client, h)
    r = client.delete(f"/api/v1/products/{p['id']}", headers=h)
    assert r.status_code == 204
    listing = client.get("/api/v1/products/", headers=h).get_json()["data"]
    assert [item["id"] for item in listing] == []
    # And direct GET returns 404
    assert client.get(f"/api/v1/products/{p['id']}", headers=h).status_code == 404


# --- POS lookup priority ----------------------------------------------------

def test_pos_lookup_priority_code_over_name(client):
    s = _signup(client)
    h = _auth(s["access"])
    # Product A: name == "999"
    a = _create_product(client, h, name="999", code="OTHER")
    # Product B: code == "999"
    b = _create_product(client, h, name="Battery", code="999")
    # Lookup "999" must hit code first, not name
    r = client.get("/api/v1/products/lookup?q=999", headers=h)
    assert r.status_code == 200
    assert r.get_json()["data"]["id"] == b["id"]


def test_pos_lookup_priority_barcode_over_name(client):
    s = _signup(client)
    h = _auth(s["access"])
    # Product A: name == "2000000000005"
    a = _create_product(client, h, name="2000000000005", code="NAMEHIT")
    # Product B: barcode == "2000000000005"
    b = _create_product(client, h, name="Cable", barcode="2000000000005")
    r = client.get("/api/v1/products/lookup?q=2000000000005", headers=h)
    assert r.status_code == 200
    assert r.get_json()["data"]["id"] == b["id"]


def test_pos_lookup_falls_back_to_exact_name(client):
    s = _signup(client)
    h = _auth(s["access"])
    p = _create_product(client, h, name="Special Item")
    r = client.get("/api/v1/products/lookup?q=Special Item", headers=h)
    assert r.status_code == 200
    assert r.get_json()["data"]["id"] == p["id"]


def test_pos_lookup_404_when_no_match(client):
    s = _signup(client)
    h = _auth(s["access"])
    r = client.get("/api/v1/products/lookup?q=does-not-exist", headers=h)
    assert r.status_code == 404


# --- Tenant isolation -------------------------------------------------------

def test_tenant_cannot_see_other_tenants_products(client):
    a = _signup(client)
    b = _signup(client)
    _create_product(client, _auth(a["access"]), name="A-only")
    listing = client.get("/api/v1/products/", headers=_auth(b["access"])).get_json()["data"]
    assert listing == []


def test_tenant_cannot_update_other_tenants_product(client):
    a = _signup(client)
    b = _signup(client)
    p = _create_product(client, _auth(a["access"]), name="A-only")
    r = client.patch(
        f"/api/v1/products/{p['id']}",
        json={"price": "1"},
        headers=_auth(b["access"]),
    )
    assert r.status_code == 404  # tenant-filter makes it invisible → not found
