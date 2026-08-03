"""Contract test for Memory agent tools (contracts/agent-tools.md).

T056 — written before agents/memory.py exists (T059/T060); MUST fail until then.
`store_preference` always creates a new version, never overwrites in place;
`get_preferences` returns only the current version per type.

Version numbers are asserted relative to each other, not as absolute 1/2 —
this suite runs against a real, persistent Postgres that may carry rows from
earlier runs (it isn't dropped between `pytest` invocations), so a fixed type
like "seat" for a fixed user may already be at version N going in.
"""

import pytest

from agents.memory import get_preferences, store_preference


@pytest.mark.asyncio
async def test_store_preference_creates_new_version_each_time():
    user_id = "traveler@example.com"
    tenant_id = "test-tenant"

    first = await store_preference(tenant_id, user_id, "seat", {"seat": "aisle"})
    second = await store_preference(tenant_id, user_id, "seat", {"seat": "window"})

    assert second["version"] == first["version"] + 1


@pytest.mark.asyncio
async def test_get_preferences_returns_only_current_version():
    user_id = "traveler@example.com"
    tenant_id = "test-tenant"

    await store_preference(tenant_id, user_id, "dietary", {"restriction": "vegetarian"})
    latest = await store_preference(tenant_id, user_id, "dietary", {"restriction": "vegan"})
    await store_preference(tenant_id, user_id, "preferred_airline", {"airline": "SV"})

    result = await get_preferences(tenant_id, user_id)
    dietary = [p for p in result["preferences"] if p["type"] == "dietary"]

    assert len(dietary) == 1
    assert dietary[0]["value"] == {"restriction": "vegan"}
    assert dietary[0]["version"] == latest["version"]
