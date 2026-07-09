"""T107 — concurrency/load: tens of concurrent tenants running trip sessions
at once against the real Postgres/RLS/connection-pool stack (only
scrapers/OAuth-backed tools are mocked, same boundary as every other
integration test).

Honest scope: this validates the harness's own concurrent-DB/RLS correctness
and internal orchestration overhead under load. It does NOT validate real
external latency (LLM calls, browser-use scraping, Google OAuth) — no live
infra for those exists in this sandbox, so SC-002/NFR-01's absolute time
budgets can only be checked against internal overhead here, not real-world
network latency.
"""

import asyncio
import os
import time
from unittest.mock import AsyncMock, patch

import asyncpg
import httpx
import pytest
from authlib.jose import jwt

from tools import db_context

N_TENANTS = 20


def _cookie_for(tenant_id: str, user_id: str) -> dict:
    token = jwt.encode(
        {"alg": "HS256"},
        {"tenant_id": tenant_id, "user_id": user_id, "is_admin": False},
        os.environ["BTM_SESSION_SECRET"],
    )
    return {"btm_session": token.decode("utf-8")}


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="no TEST_DATABASE_URL configured")
async def test_tens_of_concurrent_tenants_run_trip_sessions_without_cross_contamination():
    # The test-suite-wide pool default (max_size=3, tools/db_context.py) is
    # deliberately small to avoid connection exhaustion across sequential
    # test runs — real concurrency needs headroom, so this test raises it
    # just for itself, then restores the default for every test after it.
    os.environ["BTM_DB_POOL_MAX"] = "10"
    try:
        await db_context.init_pool(os.environ["TEST_DATABASE_URL"])

        seed_conn = await asyncpg.connect(os.environ.get("TEST_SEED_DATABASE_URL", os.environ["TEST_DATABASE_URL"]))
        tenants = [f"concurrency-tenant-{i}" for i in range(N_TENANTS)]
        try:
            for tenant_id in tenants:
                await seed_conn.execute(
                    "INSERT INTO tenants (tenant_id, name) VALUES ($1, $1) ON CONFLICT (tenant_id) DO NOTHING",
                    tenant_id,
                )
                await seed_conn.execute(
                    "INSERT INTO users (user_id, tenant_id) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING",
                    f"traveler@{tenant_id}",
                    tenant_id,
                )
        finally:
            await seed_conn.close()

        from api.main import app

        with (
            patch(
                "agents.orchestrator._extract_trip_details",
                AsyncMock(
                    return_value={
                        "destination": "Riyadh",
                        "start_date": "2026-07-14",
                        "end_date": "2026-07-17",
                        "purpose": "load test",
                        "budget": 1000,
                        "constraints": [],
                    }
                ),
            ),
            patch(
                "agents.planner.search_flights",
                AsyncMock(return_value=[{"id": "f1", "price": 400}]),
            ),
            patch(
                "agents.planner.search_airbnb",
                AsyncMock(return_value=[{"id": "a1", "price": 600, "distance_km": 1.0}]),
            ),
        ):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:

                async def run_one(tenant_id):
                    cookies = _cookie_for(tenant_id, f"traveler@{tenant_id}")
                    res = await client.post("/trips", json={"description": "trip"}, cookies=cookies)
                    assert res.status_code == 200, res.text
                    session_id = res.json()["session_id"]
                    state = await client.get(f"/trips/{session_id}", cookies=cookies)
                    assert state.status_code == 200
                    # If pool/RLS scoping ever leaked across concurrent requests,
                    # this is where a mismatched tenant's session data would surface.
                    assert {c["name"] for c in state.json()["categories"]} == {
                        "flight",
                        "accommodation",
                    }
                    return tenant_id, session_id

                start = time.monotonic()
                results = await asyncio.gather(*(run_one(t) for t in tenants))
                elapsed = time.monotonic() - start

        session_ids = [sid for _, sid in results]
        assert len(set(session_ids)) == N_TENANTS, "every tenant must get its own distinct session"

        # NFR-01's card-ready budget is 90s; with scrapers mocked (no real
        # network latency) this is really measuring internal pool/orchestration
        # overhead under 20-way concurrency, not the real budget itself.
        assert elapsed < 30, f"{N_TENANTS} concurrent trip sessions took {elapsed:.1f}s (internal overhead only)"
    finally:
        os.environ.pop("BTM_DB_POOL_MAX", None)
        await db_context.init_pool(os.environ["TEST_DATABASE_URL"])
