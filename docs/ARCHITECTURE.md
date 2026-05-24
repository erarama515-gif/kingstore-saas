# Kingstore SaaS — Architecture

> Source-of-truth for the architectural decisions taken during the Phase 1
> analysis of the legacy `E:\kingstore system Final` Flask app. Update this
> file whenever a decision changes — it is the durable record across sessions.

## 1. Goals

A multi-tenant SaaS ERP for mobile shops, inheriting the (accurate) accounting
behavior of the legacy POS but rebuilt on a production-grade modular monolith.

Non-goals (now):
* Microservices.
* Database-per-tenant.
* Kubernetes / service mesh.

## 2. Topology

```
Nginx (TLS, reverse proxy)
   │
   ├── /api/  ─────────▶  Flask + gunicorn        (modular monolith)
   │                          │
   │                          ├── PostgreSQL 16   (shared DB, tenant_id)
   │                          ├── Redis 7         (cache + rate-limit + queue)
   │                          └── Celery workers  (reports, ETL, notifications)
   │
   └── /     ──────────▶  Next.js (SSR)           (Phase F14)
```

All services run in Docker on a single VM initially. The architecture is
explicitly designed so that:
* `app` is stateless and can scale horizontally
* `db` and `redis` can be moved to managed services without app changes
* `worker` can be replicated or pinned to a different machine

## 3. Multi-tenancy

**Strategy:** Shared database, `tenant_id` column on every business table,
enforced at three layers:

1. **DB layer.** `tenant_id UUID NOT NULL` + composite indexes
   `(tenant_id, ...)` on every query path. Foreign keys with
   `ON DELETE RESTRICT` so a tenant cannot be silently cascade-deleted.
2. **ORM layer.** `TenantScopedMixin` (`app/core/db/base.py`) marks tenant-
   scoped models. A SQLAlchemy `do_orm_execute` listener uses
   `with_loader_criteria` to inject `WHERE tenant_id = g.tenant_id` into
   every SELECT — including joined/aliased loads. Repositories cannot forget
   to filter.
3. **Request layer.** The `before_request` hook in
   `app/core/tenant_context.py` decodes the JWT and populates `g.tenant_id`
   from the `tid` claim. No tenant → no auto-filter → reads return empty
   (and writes will fail FK constraints on `tenant_id`).
4. **(Future, defense in depth)** Postgres Row-Level Security policies
   matching `tenant_id = current_setting('app.tenant_id')::uuid`. Added per
   table by Alembic migrations once business tables exist.

**Bypass.** `unscoped_session()` in `app/core/db/session.py` opts out for
admin tooling, cross-tenant analytics, and the SQLite → Postgres ETL. Every
caller must justify its use.

## 4. Module layout (modular monolith)

```
app/
├── core/             cross-cutting primitives (no domain knowledge)
├── api/v1/           HTTP entry; composes module blueprints
└── modules/
    ├── auth          login, refresh, password reset
    ├── users         user CRUD, invitations, roles
    ├── tenants       organization root
    ├── branches      physical locations
    ├── products      catalog
    ├── inventory     stock + movements
    ├── customers
    ├── suppliers
    ├── sales         POS, invoices, returns
    ├── purchases     supplier inflows
    ├── repairs       maintenance tickets
    ├── expenses
    ├── treasury      cash boxes, close-day
    ├── accounting    double-entry ledger
    ├── reports       read-only over accounting
    ├── notifications
    ├── subscriptions plans, usage, billing
    └── audit_logs
```

Per-module structure:

```
modules/<name>/
    __init__.py
    models.py        SQLAlchemy ORM
    schemas.py       Pydantic DTOs
    repository.py    DB access (returns ORM objects)
    service.py       Business rules — the only public surface
    routes.py        Flask blueprint
    events.py        Domain events emitted / handled
```

Dependency rule: **modules depend on other modules only via `service.py`.**
Direct repository or model imports across modules are forbidden. Static
analysis to enforce this lands later.

## 5. Auth & RBAC

* **JWT** via `flask-jwt-extended`. Access tokens TTL 15 min, refresh tokens 7
  days. Refresh `jti` persisted in `refresh_tokens` with `revoked_at` so
  logout/rotation are real.
* **Claims:** `sub` (user_id), `tid` (tenant_id), `bid` (branch_id),
  `role`, `perms[]`, `exp`, `jti`.
* **Roles:** `owner`, `admin`, `accountant`, `cashier`, `technician`,
  `warehouse_manager`, `viewer`. Each maps to a permission set.
* **Permissions:** dotted codes like `sales.create`, `inventory.adjust`,
  `reports.financial.read`. Routes use `@require_perm("...")`.
* **Hashing:** argon2id via `argon2-cffi`. Werkzeug pbkdf2 not used.

## 6. Accounting engine (designed now, built in F3)

True double-entry. Every business mutation calls
`accounting.post_journal_entry(...)` which:

1. Creates a `JournalEntry` (header) with `date`, `reference`, `tenant_id`.
2. Inserts ≥ 2 `JournalLine` rows: `(account_id, debit, credit)`.
3. Enforces `Σ debit = Σ credit` (DB check constraint).
4. Updates `account.balance` (or computes on read — perf TBD).

**Example — cash sale of 100 EGP (COGS 60):**

| Debit              | Credit            |
|--------------------|-------------------|
| Cash             100| Sales Revenue   100|
| COGS              60| Inventory        60|

**Example — credit sale (debt):**

| Debit                | Credit            |
|----------------------|-------------------|
| Accounts Receivable 100 | Sales Revenue 100 |
| COGS              60 | Inventory       60|

**Example — owner draws 50 EGP from till (legacy `capital_withdraw`):**

| Debit                  | Credit |
|------------------------|--------|
| Owner's Drawings    50 | Cash 50|

This fixes the legacy bug where `capital_withdraw` did not reduce
`net_drawer`. P&L / trial balance / balance sheet become read-only queries
over the journal.

## 7. Key decisions inherited from legacy

* **Capital separated from operational treasury** — preserved.
* **Carry-forward via daily close** — preserved, but expressed as a
  `DayClose` event + journal entries instead of a "magic" `opening_balance`
  row.
* **Inventory valued at cost** — preserved. Cost is snapshotted into each
  sale line so renames/deletes don't break historical COGS.
* **Maintenance delivery → service revenue** — preserved as a service-layer
  event, not implicit DB row creation.

## 8. Decisions taken in scaffolding

* **Python 3.12**, Flask 3.0, SQLAlchemy 2.0 (typed mappings via
  `Mapped[...]`).
* **Pydantic v2** for DTOs and request validation, not marshmallow.
* **UUID primary keys** everywhere (`gen_random_uuid()` server-side default),
  not bigserial. Avoids ID collisions during ETL and enables client-generated
  IDs for idempotency.
* **TIMESTAMPTZ** for every time column. No naive datetimes.
* **Alembic naming convention** set on `MetaData` so constraint names are
  predictable in diffs.
* **Soft delete** opt-in per model via `SoftDeleteMixin`. Filtering deleted
  rows is the repository's responsibility, not implicit, because reporting
  and audit legitimately need tombstoned rows.

## 9. Phased roadmap

See the assistant's Phase 1 deliverable for the full F1–F16 plan. F1 (this
scaffold) provides:

* App factory, env config, extensions
* DB base, mixins, tenant scoping
* JWT + argon2 primitives, secure headers
* Tenant request context, permission decorator
* Error/JSON envelope contract
* `/api/v1/health` + `/ready`
* Alembic bootstrap
* Foundation tables (`tenants`, `branches`, `users`) — tables only, no routes
* Docker compose (db, redis, app, worker, nginx)
* Test harness with one smoke test

F2 starts when this boots clean and the smoke test passes.

## 10. Open questions (resolved before F2)

* **Refresh token rotation policy** — strict (rotate on every refresh) vs.
  sliding window. Strict by default; revisit if Next.js prefetch causes pain.
* **CSP on the API** — currently `default-src 'none'`. Fine for a JSON API
  with no HTML; revisit if we ever return rendered docs.
* **RLS rollout timing** — added per business table during F2–F8 migrations,
  not all at once. Defense-in-depth, not replacement for ORM scoping.
