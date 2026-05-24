"""Suppliers module integration tests.

Coverage mirrors customers but tests AP-side accounting:
* Opening balance posts DR Owner's Capital / CR AP and tags supplier_id
* supplier_balance() returns credit-positive payable
* AP aging shows the supplier in the right bucket
* Tenant isolation
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal

import pytest


pytestmark = pytest.mark.integration

if os.getenv("KINGSTORE_SKIP_INTEGRATION") == "1":
    pytest.skip("integration tests disabled via env", allow_module_level=True)


def _signup(client) -> dict:
    payload = {
        "tenant_slug": f"t-{uuid.uuid4().hex[:8]}",
        "tenant_name": "Suppliers Test Shop",
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


def _create_supplier(client, headers, **overrides) -> dict:
    body = {"name": "Supplier A"}
    body.update(overrides)
    body = {k: v for k, v in body.items() if v is not None}
    r = client.post("/api/v1/suppliers/", json=body, headers=headers)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["data"]


def test_create_basic(client):
    s = _signup(client)
    h = _auth(s["access"])
    sup = _create_supplier(client, h, name="ACME Mobile", phone="+202000000001",
                           contact_person="Mr. ACME")
    assert sup["name"] == "ACME Mobile"
    assert sup["contact_person"] == "Mr. ACME"


def test_opening_balance_posts_ap_journal(client):
    s = _signup(client)
    h = _auth(s["access"])
    sup = _create_supplier(client, h, name="Vendor 1", opening_balance="800.00")
    assert Decimal(sup["payable_cached"]) == Decimal("800.00")

    tb = client.get("/api/v1/accounting/trial-balance", headers=h).get_json()["data"]
    by_code = {r["code"]: r for r in tb["rows"]}
    # AP (2110) credit, Owner's Capital (3100) debit
    assert Decimal(by_code["2110"]["credit_total"]) == Decimal("800.00")
    assert Decimal(by_code["3100"]["debit_total"]) == Decimal("800.00")
    assert tb["is_balanced"] is True

    bal = client.get(f"/api/v1/suppliers/{sup['id']}/balance", headers=h).get_json()["data"]
    assert Decimal(bal["payable"]) == Decimal("800.00")


def test_ap_aging_lists_supplier_with_opening_balance(client):
    s = _signup(client)
    h = _auth(s["access"])
    _create_supplier(client, h, name="OldVendor", opening_balance="100.00")
    r = client.get("/api/v1/accounting/aging/ap", headers=h)
    assert r.status_code == 200, r.get_json()
    rows = r.get_json()["data"]
    assert len(rows) == 1
    assert rows[0]["counterparty_name"] == "OldVendor"
    # Opening balance posted today → 0-30 bucket
    assert Decimal(rows[0]["buckets"]["0-30"]) == Decimal("100.00")
    assert Decimal(rows[0]["total"]) == Decimal("100.00")


def test_supplier_statement(client):
    s = _signup(client)
    h = _auth(s["access"])
    sup = _create_supplier(client, h, name="StatementVendor", opening_balance="250.00")
    r = client.get(f"/api/v1/suppliers/{sup['id']}/statement", headers=h)
    assert r.status_code == 200
    body = r.get_json()["data"]
    assert len(body["lines"]) == 1
    # AP is credit-positive — running balance after the opening credit is +250
    assert Decimal(body["lines"][0]["credit"]) == Decimal("250.00")
    assert Decimal(body["closing_balance"]) == Decimal("250.00")


def test_quick_lookup(client):
    s = _signup(client)
    h = _auth(s["access"])
    _create_supplier(client, h, name="ACME Mobile", phone="+202000000001")
    _create_supplier(client, h, name="Tech Wholesale", phone="+202000000002")
    r = client.get("/api/v1/suppliers/lookup?q=ACME", headers=h)
    assert r.status_code == 200
    results = r.get_json()["data"]
    assert len(results) == 1
    assert results[0]["name"] == "ACME Mobile"


def test_duplicate_phone_rejected(client):
    s = _signup(client)
    h = _auth(s["access"])
    _create_supplier(client, h, phone="+202000000003")
    r = client.post(
        "/api/v1/suppliers/",
        json={"name": "Other", "phone": "+202000000003"},
        headers=h,
    )
    assert r.status_code == 409


def test_soft_delete(client):
    s = _signup(client)
    h = _auth(s["access"])
    sup = _create_supplier(client, h, name="ToDelete", phone="+202000000004")
    assert client.delete(f"/api/v1/suppliers/{sup['id']}", headers=h).status_code == 204
    assert client.get("/api/v1/suppliers/", headers=h).get_json()["data"] == []


def test_tenant_isolation(client):
    a = _signup(client)
    b = _signup(client)
    _create_supplier(client, _auth(a["access"]), name="A-only", phone="+202100000001")
    listing = client.get("/api/v1/suppliers/", headers=_auth(b["access"])).get_json()["data"]
    assert listing == []
    # And AP aging is isolated too
    aging_b = client.get(
        "/api/v1/accounting/aging/ap", headers=_auth(b["access"])
    ).get_json()["data"]
    assert aging_b == []
