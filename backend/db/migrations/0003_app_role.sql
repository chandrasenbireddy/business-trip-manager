-- CRITICAL (constitution Principle VIII): Postgres Row-Level Security policies
-- (0002_rls.sql) do NOT apply to superusers or table owners — a superuser
-- connection silently bypasses every RLS policy with no error, which would
-- make tenant isolation not-actually-structural despite 0002_rls.sql existing.
--
-- BTM_DATABASE_URL (backend/tools/db_context.py) MUST connect as this
-- non-superuser role, never as the migration-running admin/owner role.
-- Found the hard way: /speckit-implement's own verification run of
-- tests/contract/test_tenant_isolation.py passed trivially (no cross-tenant
-- leak observed) while connected as a superuser — not because RLS worked,
-- but because RLS was bypassed entirely. Re-run only caught it after
-- switching the test connection to a role exactly like this one.

CREATE ROLE btm_app LOGIN PASSWORD :'btm_app_password';  -- set via psql -v btm_app_password=... or Secret Manager in deploy tooling, never hardcoded

-- `GRANT ... ON DATABASE` needs a plain identifier, not a function call —
-- `ON DATABASE CURRENT_DATABASE()` is a syntax error (found running this
-- migration for real inside a fresh Docker container; every prior verification
-- run missed it because Postgres grants CONNECT to PUBLIC by default, so the
-- failure never blocked anything functionally). \gexec runs the dynamically
-- built statement, keeping this migration portable across database names.
SELECT format('GRANT CONNECT ON DATABASE %I TO btm_app', current_database()) \gexec
GRANT USAGE ON SCHEMA public TO btm_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO btm_app;

-- Append-only (constitution Principle X, spec NFR-05, FR-020): btm_app gets
-- no UPDATE/DELETE on approval_events, even though the blanket GRANT above
-- included it — this narrows it back.
REVOKE UPDATE, DELETE ON approval_events FROM btm_app;
