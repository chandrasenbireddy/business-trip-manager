-- Row-Level Security: structural tenant isolation (constitution Principle VIII, research.md §6).
-- Application-layer `WHERE tenant_id = ...` filtering is defense-in-depth ONLY —
-- this is the enforcement boundary a query cannot bypass, even by omission.
--
-- After this migration, re-run tests/contract/test_tenant_isolation.py (T011) and
-- confirm it now passes.

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_options ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_turns ENABLE ROW LEVEL SECURITY;
ALTER TABLE semantic_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE cost_events ENABLE ROW LEVEL SECURITY;

-- tenants/waitlist are platform-level tables with no tenant_id scoping needed
-- (tenants IS the scope; waitlist rows don't belong to a tenant yet).

CREATE POLICY tenant_isolation ON users
    USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_isolation ON sessions
    USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_isolation ON research_options
    USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_isolation ON approval_events
    USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_isolation ON conversation_turns
    USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_isolation ON semantic_memories
    USING (tenant_id = current_setting('app.tenant_id', true));
CREATE POLICY tenant_isolation ON cost_events
    USING (tenant_id = current_setting('app.tenant_id', true));

-- approval_events is additionally append-only (constitution Principle X, spec NFR-05):
-- no UPDATE or DELETE policy is defined for any role, and the application's DB role
-- MUST NOT be granted UPDATE/DELETE on this table at the database-user level either.
REVOKE UPDATE, DELETE ON approval_events FROM PUBLIC;
