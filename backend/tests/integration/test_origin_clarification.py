"""Fix: trip intake flow — full round trip through the missing-origin
clarifying question against a real Postgres. Scrapers/extraction are
mocked, same boundary as every other integration test.
"""

from unittest.mock import AsyncMock, patch

NO_ORIGIN_DETAILS = {
    "destination": "Riyadh",
    "start_date": "2026-07-14",
    "end_date": "2026-07-17",
    "purpose": "kickoff",
    "budget": 1500,
    "reference_point": "KAFD",
    "origin": None,
}


def test_missing_origin_pauses_then_resumes_after_clarify_answered(client, auth_cookies):
    # One combined patch context for the whole test, matching every other
    # integration test's pattern (e.g. test_policy_enforcement.py) — separate
    # sequential `with patch(...)` blocks around the two calls proved flaky
    # under some pytest-asyncio/TestClient thread-portal timings (search_flights/
    # search_airbnb occasionally resolved to the real, unmocked function and
    # made a real network/browser-use call). The extraction mock being "live"
    # but unused during the second call, and vice versa, is harmless.
    with (
        patch("agents.orchestrator._extract_trip_details", AsyncMock(return_value=dict(NO_ORIGIN_DETAILS))),
        patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f1", "price": 400}])),
        patch(
            "agents.planner.search_airbnb",
            AsyncMock(return_value=[{"id": "a1", "price": 600, "distance_km": 1.0}]),
        ),
    ):
        created = client.post("/trips", json={"description": "3 nights in Riyadh"}, cookies=auth_cookies).json()

        assert created["status"] == "clarifying_question"
        assert created["clarifying_question"] == "Where will you be flying from?"
        session_id = created["session_id"]
        assert session_id

        # Survives a "page refresh" — GET /trips/{id} re-derives the question
        # text from status rather than needing it passed along separately.
        state = client.get(f"/trips/{session_id}", cookies=auth_cookies).json()
        assert state["status"] == "awaiting_clarification"
        assert state["clarifying_question"] == "Where will you be flying from?"
        assert state["categories"] == []

        clarify_res = client.post(f"/trips/{session_id}/clarify", json={"answer": "Austin, TX"}, cookies=auth_cookies)
    assert clarify_res.status_code == 200
    assert clarify_res.json()["status"] == "in_progress"

    final_state = client.get(f"/trips/{session_id}", cookies=auth_cookies).json()
    assert final_state["status"] == "in_progress"
    assert {c["name"] for c in final_state["categories"]} == {"flight", "accommodation"}

    # Answered once, remembered for next time (spec: fix trip intake flow).
    prefs = client.get("/users/me/preferences", cookies=auth_cookies).json()
    assert any(p["type"] == "home_city" and p["value"]["city"] == "Austin, TX" for p in prefs["preferences"])


def test_clarify_rejects_a_session_not_awaiting_one(client, auth_cookies):
    with (
        patch(
            "agents.orchestrator._extract_trip_details",
            AsyncMock(return_value={**NO_ORIGIN_DETAILS, "origin": "Jeddah"}),
        ),
        patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f1", "price": 400}])),
        patch(
            "agents.planner.search_airbnb",
            AsyncMock(return_value=[{"id": "a1", "price": 600, "distance_km": 1.0}]),
        ),
    ):
        created = client.post("/trips", json={"description": "trip"}, cookies=auth_cookies).json()

    res = client.post(f"/trips/{created['session_id']}/clarify", json={"answer": "Austin, TX"}, cookies=auth_cookies)
    assert res.status_code == 409
