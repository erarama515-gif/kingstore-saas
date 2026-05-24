"""Integration tests for the accounting kernel.

Coverage:
* Signup seeds CoA (every system_key resolvable)
* Manual posting: balanced entry succeeds, unbalanced rejected
* Per-line: debit XOR credit, no negatives
* Trial balance reconciles to 0
* Account balance computed on natural side
* Tenant isolation: tenant A can't post to tenant B's accounts
* Reversal posts inverse and links back
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
        "tenant_name": "Acct Test Shop",
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
        "request": payload,
    }


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _accounts_by_key(client, headers) -> dict[str, dict]:
    r = client.get("/api/v1/accounting/accounts", headers=headers)
    assert r.status_code == 200
    return {a["system_key"]: a for a in r.get_json()["data"] if a["system_key"]}


# --- Tests ------------------------------------------------------------------

def test_signup_seeds_chart_of_accounts(client):
    s = _signup(client)
    by_key = _accounts_by_key(client, _auth(s["access"]))
    # All required system accounts must be present
    for key in (
        "CASH", "BANK", "AR", "AP", "INVENTORY",
        "SALES_REVENUE", "SERVICE_REVENUE", "COGS",
        "OPERATING_EXPENSES", "OWNER_CAPITAL", "OWNER_DRAWINGS",
        "RETAINED_EARNINGS",
    ):
        assert key in by_key, f"system_key {key!r} missing from seeded CoA"


def test_post_balanced_journal_entry_succeeds(client):
    s = _signup(client)
    h = _auth(s["access"])
    by_key = _accounts_by_key(client, h)

    # Owner injects 5000 EGP capital: DR Cash / CR Owner's Capital
    payload = {
        "entry_date": "2026-05-24",
        "branch_id": s["branch_id"],
        "reference": "INIT-CAP",
        "description": "Initial capital injection",
        "lines": [
            {"account_id": by_key["CASH"]["id"], "debit": "5000.00", "credit": "0"},
            {"account_id": by_key["OWNER_CAPITAL"]["id"], "debit": "0", "credit": "5000.00"},
        ],
    }
    r = client.post("/api/v1/accounting/journal-entries", json=payload, headers=h)
    assert r.status_code == 201, r.get_json()
    body = r.get_json()["data"]
    assert body["source"] == "manual"
    assert len(body["lines"]) == 2
    assert body["posted_at"]


def test_unbalanced_entry_is_rejected(client):
    s = _signup(client)
    h = _auth(s["access"])
    by_key = _accounts_by_key(client, h)
    payload = {
        "entry_date": "2026-05-24",
        "lines": [
            {"account_id": by_key["CASH"]["id"], "debit": "100.00", "credit": "0"},
            {"account_id": by_key["OWNER_CAPITAL"]["id"], "debit": "0", "credit": "99.99"},
        ],
    }
    r = client.post("/api/v1/accounting/journal-entries", json=payload, headers=h)
    assert r.status_code == 422  # Pydantic catches the imbalance


def test_line_with_both_debit_and_credit_is_rejected(client):
    s = _signup(client)
    h = _auth(s["access"])
    by_key = _accounts_by_key(client, h)
    payload = {
        "entry_date": "2026-05-24",
        "lines": [
            {"account_id": by_key["CASH"]["id"], "debit": "10", "credit": "10"},
            {"account_id": by_key["OWNER_CAPITAL"]["id"], "debit": "0", "credit": "10"},
        ],
    }
    r = client.post("/api/v1/accounting/journal-entries", json=payload, headers=h)
    assert r.status_code == 422


def test_negative_amount_rejected(client):
    s = _signup(client)
    h = _auth(s["access"])
    by_key = _accounts_by_key(client, h)
    payload = {
        "entry_date": "2026-05-24",
        "lines": [
            {"account_id": by_key["CASH"]["id"], "debit": "-100", "credit": "0"},
            {"account_id": by_key["OWNER_CAPITAL"]["id"], "debit": "0", "credit": "-100"},
        ],
    }
    r = client.post("/api/v1/accounting/journal-entries", json=payload, headers=h)
    assert r.status_code == 422


def test_trial_balance_reconciles_to_zero(client):
    s = _signup(client)
    h = _auth(s["access"])
    by_key = _accounts_by_key(client, h)

    # Post a few entries
    for cash, equity in [("3000", "3000"), ("1500.50", "1500.50")]:
        client.post(
            "/api/v1/accounting/journal-entries",
            json={
                "entry_date": "2026-05-24",
                "lines": [
                    {"account_id": by_key["CASH"]["id"], "debit": cash, "credit": "0"},
                    {"account_id": by_key["OWNER_CAPITAL"]["id"], "debit": "0", "credit": equity},
                ],
            },
            headers=h,
        )

    r = client.get("/api/v1/accounting/trial-balance", headers=h)
    assert r.status_code == 200
    tb = r.get_json()["data"]
    assert tb["is_balanced"] is True
    assert Decimal(tb["debit_grand_total"]) == Decimal("4500.50")
    assert Decimal(tb["credit_grand_total"]) == Decimal("4500.50")


def test_account_balance_uses_natural_side(client):
    s = _signup(client)
    h = _auth(s["access"])
    by_key = _accounts_by_key(client, h)

    client.post(
        "/api/v1/accounting/journal-entries",
        json={
            "entry_date": "2026-05-24",
            "lines": [
                {"account_id": by_key["CASH"]["id"], "debit": "100", "credit": "0"},
                {"account_id": by_key["OWNER_CAPITAL"]["id"], "debit": "0", "credit": "100"},
            ],
        },
        headers=h,
    )
    # Cash (asset, debit-positive): balance = debit - credit = +100
    r1 = client.get(
        f"/api/v1/accounting/accounts/{by_key['CASH']['id']}/balance", headers=h
    )
    assert Decimal(r1.get_json()["data"]["balance"]) == Decimal("100")

    # Owner's Capital (equity, credit-positive): balance = credit - debit = +100
    r2 = client.get(
        f"/api/v1/accounting/accounts/{by_key['OWNER_CAPITAL']['id']}/balance", headers=h
    )
    assert Decimal(r2.get_json()["data"]["balance"]) == Decimal("100")


def test_cross_tenant_account_post_is_rejected(client):
    a = _signup(client)
    b = _signup(client)
    a_by_key = _accounts_by_key(client, _auth(a["access"]))
    # Tenant B tries to post against tenant A's account ids:
    payload = {
        "entry_date": "2026-05-24",
        "lines": [
            {"account_id": a_by_key["CASH"]["id"], "debit": "10", "credit": "0"},
            {"account_id": a_by_key["OWNER_CAPITAL"]["id"], "debit": "0", "credit": "10"},
        ],
    }
    r = client.post(
        "/api/v1/accounting/journal-entries", json=payload, headers=_auth(b["access"])
    )
    # Should be 400 (unknown accounts in our tenant) — definitely not 201
    assert r.status_code in (400, 404, 422), r.get_json()


def test_reversal_inverts_lines_and_links_back(client):
    s = _signup(client)
    h = _auth(s["access"])
    by_key = _accounts_by_key(client, h)

    # Post original
    r = client.post(
        "/api/v1/accounting/journal-entries",
        json={
            "entry_date": "2026-05-24",
            "reference": "ORIG-1",
            "lines": [
                {"account_id": by_key["CASH"]["id"], "debit": "200", "credit": "0"},
                {"account_id": by_key["OWNER_CAPITAL"]["id"], "debit": "0", "credit": "200"},
            ],
        },
        headers=h,
    )
    orig = r.get_json()["data"]
    orig_id = orig["id"]

    # Reverse
    r2 = client.post(
        f"/api/v1/accounting/journal-entries/{orig_id}/reverse",
        json={"reason": "data entry error"},
        headers=h,
    )
    assert r2.status_code == 201
    rev = r2.get_json()["data"]
    assert rev["reverses_id"] == orig_id
    assert rev["source"] == "reversal"
    # Inverted lines: original debit becomes credit and vice versa
    rev_by_acct = {l["account_id"]: l for l in rev["lines"]}
    assert Decimal(rev_by_acct[by_key["CASH"]["id"]]["credit"]) == Decimal("200")
    assert Decimal(rev_by_acct[by_key["OWNER_CAPITAL"]["id"]]["debit"]) == Decimal("200")

    # After reversal, trial balance should be back to zero net (debits=credits=400)
    tb = client.get("/api/v1/accounting/trial-balance", headers=h).get_json()["data"]
    assert tb["is_balanced"] is True
    assert Decimal(tb["debit_grand_total"]) == Decimal("400")


def test_reversal_cannot_be_reversed(client):
    s = _signup(client)
    h = _auth(s["access"])
    by_key = _accounts_by_key(client, h)
    orig = client.post(
        "/api/v1/accounting/journal-entries",
        json={
            "entry_date": "2026-05-24",
            "lines": [
                {"account_id": by_key["CASH"]["id"], "debit": "50", "credit": "0"},
                {"account_id": by_key["OWNER_CAPITAL"]["id"], "debit": "0", "credit": "50"},
            ],
        },
        headers=h,
    ).get_json()["data"]
    rev = client.post(
        f"/api/v1/accounting/journal-entries/{orig['id']}/reverse",
        json={"reason": "first reversal"},
        headers=h,
    ).get_json()["data"]
    r3 = client.post(
        f"/api/v1/accounting/journal-entries/{rev['id']}/reverse",
        json={"reason": "double reversal"},
        headers=h,
    )
    assert r3.status_code == 400
