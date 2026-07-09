"""DEV_BYPASS (api/middleware/auth.py): local-dev-only escape hatch that
auto-attaches a dev session to every request and skips the whole
waitlist/OAuth onboarding gate. MUST default off — this is as much a
regression guard against DEV_BYPASS ever accidentally defaulting to enabled
as it is a test of the feature itself.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

import api.middleware.auth as auth_middleware


@pytest.fixture(autouse=True)
def _reset_dev_bypass_state():
    # conftest.py already forces api.main's import (and the load_dotenv()
    # side effect that comes with it) at collection time and clears
    # DEV_BYPASS right after — safe to just pop/reset here per-test.
    #
    # The "ensure the dev user exists" check is cached process-wide (module
    # global) so it only costs a DB round trip once — reset it around every
    # test so one test enabling DEV_BYPASS can't leak a stale "already
    # ensured" flag into another.
    auth_middleware._dev_user_ensured = False
    os.environ.pop("DEV_BYPASS", None)
    yield
    auth_middleware._dev_user_ensured = False
    os.environ.pop("DEV_BYPASS", None)


def test_dev_bypass_off_by_default_normal_auth_still_enforced(client):
    res = client.get("/users/me")
    assert res.status_code == 401


def test_dev_bypass_requires_the_exact_string_true(client):
    os.environ["DEV_BYPASS"] = "1"  # truthy-looking, but not "true"
    res = client.get("/users/me")
    assert res.status_code == 401


def test_dev_bypass_true_auto_attaches_a_dev_session_with_no_cookie(client):
    os.environ["DEV_BYPASS"] = "true"
    res = client.get("/users/me")
    assert res.status_code == 200
    body = res.json()
    assert body["user_id"] == "dev@localhost"
    assert body["tenant_id"] == "dev-tenant"
    assert body["is_admin"] is True


def test_dev_bypass_reaches_a_normally_admin_only_route_too(client):
    os.environ["DEV_BYPASS"] = "true"
    res = client.get("/admin/policy")
    assert res.status_code == 200


def test_dev_bypass_can_create_a_real_trip_with_no_waitlist_or_oauth_at_all(client):
    """The actual point of DEV_BYPASS — skip waitlist submit -> admin
    approve -> OAuth consent entirely and go straight to using the feature,
    with no cookie, no waitlist entry, no session created via /auth/callback.
    """
    os.environ["DEV_BYPASS"] = "true"
    with (
        patch(
            "agents.orchestrator._extract_trip_details",
            AsyncMock(
                return_value={
                    "destination": "Riyadh",
                    "start_date": "2026-07-14",
                    "end_date": "2026-07-17",
                    "purpose": "dev testing",
                    "budget": 1000,
                    "origin": "Dev City",
                }
            ),
        ),
        patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f1", "price": 400}])),
        patch(
            "agents.planner.search_airbnb",
            AsyncMock(return_value=[{"id": "a1", "price": 600, "distance_km": 1.0}]),
        ),
    ):
        res = client.post("/trips", json={"description": "trip"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "in_progress"
    assert body["session_id"]
