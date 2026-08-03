"""Contract test for POST /trips/{id}/categories/{category}/research (contracts/bff-api.md).

T048 — written before the endpoint exists (T053); MUST fail until then.
"""

from unittest.mock import AsyncMock, patch

RIYADH_DETAILS = {
    "destination": "Riyadh",
    "start_date": "2026-11-10",
    "end_date": "2026-11-13",
    "purpose": "conference",
    "budget": 1200,
    "origin": "Dammam",
    "constraints": [],
}


def _create_trip(client, cookies):
    with (
        patch("agents.orchestrator._extract_trip_details", AsyncMock(return_value=RIYADH_DETAILS)),
        patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f1", "price": 400}])),
        patch(
            "agents.planner.search_airbnb",
            AsyncMock(return_value=[{"id": "a1", "price": 600, "distance_km": 1.2}]),
        ),
    ):
        return client.post("/trips", json={"description": "3 nights in Riyadh"}, cookies=cookies).json()


def test_research_category_returns_researching_status(client, auth_cookies):
    created = _create_trip(client, auth_cookies)

    with patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f2", "price": 450}])):
        res = client.post(
            f"/trips/{created['session_id']}/categories/flight/research",
            json={"reason": "too expensive"},
            cookies=auth_cookies,
        )
    assert res.status_code == 200
    assert res.json()["status"] == "researching"


def test_research_category_after_cap_returns_manual_fallback(client, auth_cookies):
    created = _create_trip(client, auth_cookies)
    session_id = created["session_id"]

    # Already at attempt 1 (from _create_trip). Two more re-searches bring it to
    # attempt 3 — the cap. A 4th call (this test's third `research` call) must
    # return manual_fallback instead of searching again.
    with patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f2", "price": 450}])):
        client.post(
            f"/trips/{session_id}/categories/flight/research",
            json={"reason": "no"},
            cookies=auth_cookies,
        )
    with patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f3", "price": 500}])):
        client.post(
            f"/trips/{session_id}/categories/flight/research",
            json={"reason": "no"},
            cookies=auth_cookies,
        )

    with patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f4", "price": 550}])) as mock_search:
        res = client.post(
            f"/trips/{session_id}/categories/flight/research",
            json={"reason": "still no"},
            cookies=auth_cookies,
        )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "manual_fallback"
    assert len(body["best_options"]) > 0
    mock_search.assert_not_called()
