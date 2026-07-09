"""Constitution Principle VIII: tenant isolation must be structural (RLS), not a filter.

T011 — write first, confirm it fails. Before db/migrations/0002_rls.sql (T012) is
applied, this test MUST fail: querying through tenant_connection(tenant_a) with
no WHERE clause returns rows from every tenant, because nothing enforces scoping
yet. After T012 lands, the same query returns only tenant_a's rows.

Requires a live Postgres reachable via TEST_DATABASE_URL (a non-superuser role
— RLS policies do not apply to superusers/table owners, so testing as one
would always "pass" without proving anything) with migrations 0001 and 0002
applied. Skipped otherwise — this is a real integration test against RLS, not
something a unit-test mock can substitute for.
"""

import os
import uuid

import asyncpg
import pytest

from tools import db_context

TEST_DSN = os.environ.get("TEST_DATABASE_URL")
# Seeding must bypass RLS (it isn't scoped to one tenant_id session variable) —
# this MUST be a superuser/elevated role, distinct from TEST_DATABASE_URL.
SEED_DSN = os.environ.get("TEST_SEED_DATABASE_URL", TEST_DSN)

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="TEST_DATABASE_URL not configured")


@pytest.fixture
async def two_tenants_with_sessions():
    conn = await asyncpg.connect(SEED_DSN)
    tenant_a, tenant_b = f"tenant-a-{uuid.uuid4()}", f"tenant-b-{uuid.uuid4()}"
    for tid in (tenant_a, tenant_b):
        await conn.execute("INSERT INTO tenants (tenant_id, name) VALUES ($1, $1)", tid)
        await conn.execute(
            "INSERT INTO users (user_id, tenant_id) VALUES ($1, $2)", f"user-{tid}", tid
        )
        await conn.execute(
            "INSERT INTO sessions (session_id, user_id, tenant_id, status, trip_request) "
            "VALUES ($1, $2, $3, 'in_progress', '{}'::jsonb)",
            f"session-{tid}",
            f"user-{tid}",
            tid,
        )
    yield tenant_a, tenant_b
    await conn.execute("DELETE FROM sessions WHERE tenant_id = ANY($1)", [tenant_a, tenant_b])
    await conn.execute("DELETE FROM users WHERE tenant_id = ANY($1)", [tenant_a, tenant_b])
    await conn.execute("DELETE FROM tenants WHERE tenant_id = ANY($1)", [tenant_a, tenant_b])
    await conn.close()


async def test_query_without_tenant_scope_is_isolated(two_tenants_with_sessions):
    tenant_a, tenant_b = two_tenants_with_sessions

    await db_context.init_pool(TEST_DSN)
    async with db_context.tenant_connection(tenant_a) as conn:
        # Deliberately no `WHERE tenant_id = $1` — isolation must come from RLS,
        # not from every caller remembering to filter (constitution Principle VIII).
        rows = await conn.fetch("SELECT tenant_id FROM sessions")

    seen_tenants = {row["tenant_id"] for row in rows}
    assert tenant_a in seen_tenants
    assert tenant_b not in seen_tenants, (
        "Cross-tenant row leaked — RLS policy (0002_rls.sql) is missing or not applied"
    )
