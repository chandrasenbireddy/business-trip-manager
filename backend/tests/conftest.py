"""Shared test fixtures. BTM_SESSION_SECRET/BTM_DATABASE_URL are set here so
api.main can import (and its lifespan can start) without real deployment
config during tests.
"""

import os

os.environ.setdefault("BTM_SESSION_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("BTM_DATABASE_URL", os.environ.get("TEST_DATABASE_URL", ""))

# browser_use (imported transitively via scrapers/flights.py ->
# agents/planner.py -> agents/orchestrator.py -> api.main) calls
# load_dotenv() at ITS OWN module import time, which happens exactly once
# per process — the first thing anywhere in the whole test session to
# import api.main pulls the developer's real .env into os.environ. If that
# .env has DEV_BYPASS=true (api/middleware/auth.py) set for local dev, every
# test after that first import would otherwise silently run with
# authentication bypassed instead of the tenant/user the test actually
# expects. Force that import here, at collection time, before any test
# fixture (or test body) runs, then immediately undo the one var that
# matters for test correctness.
import api.main  # noqa: E402, F401

os.environ.pop("DEV_BYPASS", None)

import asyncpg
import pytest
from authlib.jose import jwt
from fastapi.testclient import TestClient

from tools import db_context
from tools.telemetry import RunContext, run_context

TEST_DSN = os.environ.get("TEST_DATABASE_URL")
# Seeding fixture data must bypass RLS (it isn't scoped to any one tenant_id
# session variable) — this MUST be a superuser/elevated role, never the
# app's own restricted role (TEST_DATABASE_URL), or RLS correctly rejects it.
SEED_DSN = os.environ.get("TEST_SEED_DATABASE_URL", TEST_DSN)


@pytest.fixture
def client():
    """Entering as a context manager fires FastAPI's lifespan (startup/shutdown),
    which is what actually creates the asyncpg pool (api/main.py) — the pool
    MUST be created in the same event loop TestClient uses to run the app, or
    asyncpg raises "another operation is in progress" on first use.
    """
    from api.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
async def _seed_test_tenant():
    """HTTP-level tests authenticate as tenant_id=test-tenant /
    user_id=traveler@example.com|admin@example.com — those rows must exist for
    the sessions table's FK constraints to accept a real INSERT. Skipped
    (no-op) when no TEST_DATABASE_URL is configured, same as
    test_tenant_isolation.py. Uses its own connection, not the app's pool —
    this runs before the `client` fixture (if any) enters the app's lifespan.

    Also (re-)initializes tools.db_context's pool for every test, in that
    test's own event loop — otherwise a test that calls an agent/model
    function directly (bypassing the `client` fixture's app lifespan, which
    is the only other thing that inits the pool) inherits a pool bound to
    the closed loop of whichever earlier test's `client` fixture last set it,
    and asyncpg raises "another operation is in progress" on first use.
    """
    if not TEST_DSN:
        yield
        return

    await db_context.init_pool(TEST_DSN)
    conn = await asyncpg.connect(SEED_DSN)
    await conn.execute("INSERT INTO tenants (tenant_id, name) VALUES ('test-tenant', 'test-tenant') ON CONFLICT (tenant_id) DO NOTHING")
    # US4 added mutable, persistent tenant policy state (PUT /admin/policy).
    # Tests written before US4 assume no filtering/approval-gating happens —
    # reset it here so a policy one test sets can never leak into another
    # test that shares this same tenant row and doesn't expect one.
    await conn.execute("UPDATE tenants SET travel_policy = '{}' WHERE tenant_id = 'test-tenant'")
    for user_id in ("traveler@example.com", "admin@example.com"):
        await conn.execute(
            "INSERT INTO users (user_id, tenant_id) VALUES ($1, 'test-tenant') ON CONFLICT (user_id) DO NOTHING",
            user_id,
        )
    # Same leak as travel_policy above, different table: store_preference
    # (fix: trip intake flow's home_city) never overwrites, only adds new
    # versions — a preference one test stores for traveler@example.com
    # otherwise persists in this real, non-dropped-between-runs Postgres and
    # gets silently reused by every later test sharing this same seeded user,
    # even across separate pytest invocations.
    await conn.execute("DELETE FROM semantic_memories WHERE tenant_id = 'test-tenant'")
    await conn.close()
    yield


@pytest.fixture(autouse=True)
def _ambient_run_context():
    """Every @traced call needs a RunContext (constitution Principle XV).
    HTTP-level tests get a real one from SessionAuthMiddleware; tests that call
    an agent/tool function directly (e.g. test_booking_gate.py) need this
    fallback so they exercise the function under test, not telemetry plumbing.
    """
    with run_context(
        RunContext(
            tenant_id="test-tenant",
            session_id="test-session",
            agent_id="test",
            agent_version="0.0.0",
            graph_run_id="test-run",
        )
    ):
        yield


@pytest.fixture
def auth_cookies():
    """A valid session cookie for a non-admin traveler in a test tenant."""
    token = jwt.encode(
        {"alg": "HS256"},
        {"tenant_id": "test-tenant", "user_id": "traveler@example.com", "is_admin": False},
        os.environ["BTM_SESSION_SECRET"],
    )
    return {"btm_session": token.decode("utf-8")}


@pytest.fixture
def admin_cookies():
    token = jwt.encode(
        {"alg": "HS256"},
        {"tenant_id": "test-tenant", "user_id": "admin@example.com", "is_admin": True},
        os.environ["BTM_SESSION_SECRET"],
    )
    return {"btm_session": token.decode("utf-8")}
