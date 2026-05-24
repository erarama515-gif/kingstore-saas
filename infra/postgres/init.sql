-- =============================================================================
-- Kingstore SaaS — Postgres bootstrap
-- Runs once when the postgres container initializes a fresh data dir.
-- =============================================================================

-- gen_random_uuid() and crypto helpers
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Case-insensitive text (used for username/email columns)
CREATE EXTENSION IF NOT EXISTS citext;

-- Used by some indexes for tenant + JSONB columns later
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- A dedicated test database for the pytest integration suite. We grant it
-- explicitly so `flask db upgrade` in the test session can create tables.
CREATE DATABASE kingstore_test OWNER kingstore;

-- =============================================================================
-- Row-Level Security policies are *defined here as a placeholder*. The actual
-- policies will be created by Alembic migrations once business tables exist
-- (Phase F2+). Defining them here would fail because the tables don't yet
-- exist on a fresh schema. The pattern is captured in docs/ARCHITECTURE.md.
-- =============================================================================
