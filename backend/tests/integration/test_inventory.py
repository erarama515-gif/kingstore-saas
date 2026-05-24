"""Inventory module integration tests.

Coverage:
* Manual adjust IN: stock created, qty correct, journal entry posted
  (DR Inventory / CR Owner's Capital)
* Manual adjust OUT: stock decremented, journal posted
  (DR Operating Expenses / CR Inventory)
* Adjust OUT blocked when insufficient stock
* Adjust OUT on uninitialized product → 404
* Movement history listed in reverse chronological order
* Stock-level read for an unknown (product, branch) returns 0 (not 404)
* Cross-tenant: tenant A can't adjust tenant B's product
* Trial balance stays balanced after adjustments
* avg_cost recomputes correctly across two purchases at different costs
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
        "tenant_name": "Inventory Test Shop",
        "owner_name": "Owner",
        "owner_email": f"owner-{uuid.uuid4().hex[:6]}@example.com",
        "owner_username": f"owner{uuid.uuid4().hex[:6]}",
        "owner_password": "CorrectHorse1Battery",
        "default_branch_name": "Main",
        "default_branch_code": "MAIN",
    }
    resp = client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 201, resp.get_json()
    d = resp.get_json()["data"]
    return {
        "tenant_id": d["tenant"]["id"],
        "branch_id": d["user"]["default_branch_id"],
        "access": d["tokens"]["access_token"],
    }


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_product(client, headers, cost="100.00", price="150.00", **k) -> dict:
    body = {
        "name": k.get("name", "Test"),
        "category": k.get("category", "mobile"),
        "cost": cost,
        "price": price,
    }
    r = client.post("/api/v1/products/", json=body, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["data"]


def _adjust(client, headers, product_id, branch_id, qty, direction, **k):
    body = {
        "product_id": product_id,
        "branch_id": branch_id,
        "qty": qty,
        "direction": direction,
        "reason": k.get("reason", "test"),
    }
    if "unit_cost" in k:
        body["unit_cost"] = k["unit_cost"]
    return client.post("/api/v1/inventory/adjust", json=body, headers=headers)


def _stock_level(client, headers, product_id, branch_id):
    r = client.get(
        f"/api/v1/inventory/stock-levels/{product_id}/{branch_id}",
        headers=headers,
    )
    assert r.status_code == 200, r.get_json()
    return r.get_json()["data"]


# --- Tests ------------------------------------------------------------------

def test_adjust_in_creates_stock_and_posts_journal(client):
    s = _signup(client)
    h = _auth(s["access"])
    p = _create_product(client, h, cost="100.00")
    r = _adjust(client, h, p["id"], s["branch_id"], qty=10, direction="in")
    assert r.status_code == 201, r.get_json()
    body = r.get_json()["data"]
    assert body["new_qty"] == 10
    assert body["journal_entry_id"]

    # Stock level reflects the change
    level = _stock_level(client, h, p["id"], s["branch_id"])
    assert level["qty_on_hand"] == 10

    # Trial balance: DR Inventory 1000 / CR Owner's Capital 1000 → balanced
    tb = client.get("/api/v1/accounting/trial-balance", headers=h).get_json()["data"]
    assert tb["is_balanced"] is True
    by_code = {r["code"]: r for r in tb["rows"]}
    assert Decimal(by_code["1140"]["debit_total"]) == Decimal("1000.00")  # Inventory
    assert Decimal(by_code["3100"]["credit_total"]) == Decimal("1000.00")  # Owner's Capital


def test_adjust_out_decrements_and_posts(client):
    s = _signup(client)
    h = _auth(s["access"])
    p = _create_product(client, h, cost="50.00")
    _adjust(client, h, p["id"], s["branch_id"], qty=10, direction="in")
    r = _adjust(client, h, p["id"], s["branch_id"], qty=4, direction="out",
                reason="damage")
    assert r.status_code == 201
    assert r.get_json()["data"]["new_qty"] == 6

    tb = client.get("/api/v1/accounting/trial-balance", headers=h).get_json()["data"]
    assert tb["is_balanced"] is True
    by_code = {r["code"]: r for r in tb["rows"]}
    # Inventory: +500 in, -200 out → net debit 300
    assert Decimal(by_code["1140"]["balance"]) == Decimal("300.00")
    # Operating Expenses: 200 (the loss)
    assert Decimal(by_code["5200"]["balance"]) == Decimal("200.00")


def test_adjust_out_blocked_on_insufficient_stock(client):
    s = _signup(client)
    h = _auth(s["access"])
    p = _create_product(client, h)
    _adjust(client, h, p["id"], s["branch_id"], qty=3, direction="in")
    r = _adjust(client, h, p["id"], s["branch_id"], qty=10, direction="out")
    assert r.status_code == 400
    assert "insufficient" in r.get_json()["error"]["message"].lower()


def test_adjust_out_on_uninitialized_product_is_404(client):
    s = _signup(client)
    h = _auth(s["access"])
    p = _create_product(client, h)
    # Never added inbound stock for this branch
    r = _adjust(client, h, p["id"], s["branch_id"], qty=1, direction="out")
    assert r.status_code == 404


def test_stock_level_for_unknown_pair_returns_zero(client):
    s = _signup(client)
    h = _auth(s["access"])
    p = _create_product(client, h)
    level = _stock_level(client, h, p["id"], s["branch_id"])
    assert level["qty_on_hand"] == 0


def test_movements_listed_reverse_chronological(client):
    s = _signup(client)
    h = _auth(s["access"])
    p = _create_product(client, h)
    _adjust(client, h, p["id"], s["branch_id"], qty=5, direction="in", reason="first")
    _adjust(client, h, p["id"], s["branch_id"], qty=2, direction="out", reason="second")
    _adjust(client, h, p["id"], s["branch_id"], qty=1, direction="in", reason="third")

    r = client.get(
        f"/api/v1/inventory/products/{p['id']}/movements?per_page=10",
        headers=h,
    )
    assert r.status_code == 200
    items = r.get_json()["data"]
    assert len(items) == 3
    # Most recent first
    assert items[0]["notes"] == "third"
    assert items[-1]["notes"] == "first"


def test_avg_cost_weighted_across_two_inbounds(client):
    s = _signup(client)
    h = _auth(s["access"])
    p = _create_product(client, h, cost="100.00")
    # First inbound 10 units @ 100 → avg = 100
    _adjust(client, h, p["id"], s["branch_id"], qty=10, direction="in",
            unit_cost="100.00")
    # Second inbound 10 units @ 200 → avg = (10*100 + 10*200) / 20 = 150
    _adjust(client, h, p["id"], s["branch_id"], qty=10, direction="in",
            unit_cost="200.00")
    level = _stock_level(client, h, p["id"], s["branch_id"])
    assert level["qty_on_hand"] == 20
    assert Decimal(level["avg_cost"]) == Decimal("150.0000")


def test_tenant_isolation_on_adjust(client):
    a = _signup(client)
    b = _signup(client)
    p = _create_product(client, _auth(a["access"]), name="A's product")
    # Tenant B tries to add stock for tenant A's product
    r = _adjust(client, _auth(b["access"]), p["id"], b["branch_id"], qty=5, direction="in")
    # Product not found under tenant B's scope
    assert r.status_code in (400, 404)
