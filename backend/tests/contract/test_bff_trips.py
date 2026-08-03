"""Contract test for POST /trips and GET /trips/{id} (contracts/bff-api.md).

T025 — written before api/routes/trips.py exists (T037); MUST fail until then.
NLU extraction and the scrapers are mocked — this test is about the BFF's
contract shape, not the orchestrator's NLU or the scrapers' own behavior
(those are test_scraper_tools.py's and orchestrator's own concern).
"""

from unittest.mock import AsyncMock, patch

import pytest

RIYADH_DETAILS = {
    "destination": "Riyadh",
    "start_date": "2026-11-10",
    "end_date": "2026-11-13",
    "purpose": "conference",
    "budget": 1200,
    "origin": "Dammam",
    "constraints": [],
}


@pytest.fixture
def mocked_research():
    with (
        patch("agents.orchestrator._extract_trip_details", AsyncMock(return_value=RIYADH_DETAILS)),
        patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f1", "price": 400}])),
        patch(
            "agents.planner.search_airbnb",
            AsyncMock(return_value=[{"id": "a1", "price": 600, "distance_km": 1.2}]),
        ),
    ):
        yield


def test_post_trips_returns_session_id(client, auth_cookies, mocked_research):
    res = client.post("/trips", json={"description": "3 nights in Riyadh near KAFD"}, cookies=auth_cookies)
    assert res.status_code == 200
    body = res.json()
    assert "session_id" in body
    assert body["status"] in ("in_progress", "clarifying_question")


def test_post_trips_ambiguous_request_asks_one_clarifying_question(client, auth_cookies):
    with patch(
        "agents.orchestrator._extract_trip_details",
        AsyncMock(return_value={"destination": None, "start_date": None, "end_date": None}),
    ):
        res = client.post("/trips", json={"description": "book me a trip"}, cookies=auth_cookies)
    body = res.json()
    assert isinstance(body["clarifying_question"], str)


def test_get_trip_returns_categories(client, auth_cookies, mocked_research):
    created = client.post("/trips", json={"description": "3 nights in Riyadh near KAFD"}, cookies=auth_cookies).json()
    res = client.get(f"/trips/{created['session_id']}", cookies=auth_cookies)
    assert res.status_code == 200
    body = res.json()
    assert "status" in body
    assert "categories" in body
