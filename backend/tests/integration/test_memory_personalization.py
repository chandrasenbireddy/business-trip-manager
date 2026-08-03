"""Integration test: a preference stated in trip N is applied automatically in
trip N+1 without the traveler restating it (spec Story 3, acceptance scenario 1).

T057 — written before the Story 3 implementation tasks (T058-T063) exist;
MUST fail until then.
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


def test_seat_preference_applied_to_next_trip_without_restating(client, auth_cookies):
    # Trip N: state a seat preference explicitly (spec Story 3, acceptance scenario 3's
    # mechanism — profile settings — is exactly what makes scenario 1 possible).
    pref_res = client.patch("/users/me/preferences/seat", json={"value": {"seat": "aisle"}}, cookies=auth_cookies)
    assert pref_res.status_code == 200
    assert isinstance(pref_res.json()["version"], int)

    # Trip N+1: an unrelated new trip request — the traveler never mentions seat again.
    with patch("agents.orchestrator._extract_trip_details", AsyncMock(return_value=RIYADH_DETAILS)):
        with patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f1", "price": 400}])) as mock_flights:
            with patch(
                "agents.planner.search_airbnb",
                AsyncMock(return_value=[{"id": "a1", "price": 600, "distance_km": 1.2}]),
            ):
                client.post("/trips", json={"description": "3 nights in Riyadh"}, cookies=auth_cookies)

    # First-pass results already reflect the preference (spec Story 3, scenario 1) —
    # the search call the planner made carries it, without the traveler restating it.
    _, kwargs = mock_flights.call_args
    assert "aisle" in kwargs.get("notes", "")
