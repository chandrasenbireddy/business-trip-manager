"""Integration test: reject all options in one category 3 times -> manual
fallback offered; the other category's state is untouched throughout
(spec FR-007/FR-008).

T049 — written before the Story 2 implementation tasks (T050-T053) exist;
MUST fail until then.
"""

from unittest.mock import AsyncMock, patch

RIYADH_DETAILS = {
    "destination": "Riyadh",
    "start_date": "2026-11-10",
    "end_date": "2026-11-13",
    "purpose": "conference",
    "budget": 1200,
    "constraints": [],
}


def test_reject_all_three_times_triggers_manual_fallback_other_category_untouched(client, auth_cookies):
    with (
        patch("agents.orchestrator._extract_trip_details", AsyncMock(return_value=RIYADH_DETAILS)),
        patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f1", "price": 400}])),
        patch(
            "agents.planner.search_airbnb",
            AsyncMock(return_value=[{"id": "a1", "price": 600, "distance_km": 1.2}]),
        ),
    ):
        created = client.post("/trips", json={"description": "3 nights in Riyadh"}, cookies=auth_cookies).json()
    session_id = created["session_id"]

    state = client.get(f"/trips/{session_id}", cookies=auth_cookies).json()
    accommodation_option = next(c for c in state["categories"] if c["name"] == "accommodation")["options"][0]

    # Attempt 1 (initial) is already shown. Rejecting it re-searches into
    # attempt 2, rejecting THAT re-searches into attempt 3 — 2 successful
    # re-searches. Rejecting attempt 3 is the 3rd rejection: the cap is hit,
    # so that 3rd research call returns manual_fallback with no 4th search.
    for i, price in enumerate((410, 420), start=2):
        flight_option = next(
            c for c in client.get(f"/trips/{session_id}", cookies=auth_cookies).json()["categories"] if c["name"] == "flight"
        )["options"][0]
        client.post(
            f"/trips/{session_id}/options/{flight_option['option_id']}/decision",
            json={"decision": "rejected"},
            cookies=auth_cookies,
        )
        with patch(
            "agents.planner.search_flights",
            AsyncMock(return_value=[{"id": f"f{i}", "price": price}]),
        ):
            res = client.post(
                f"/trips/{session_id}/categories/flight/research",
                json={"reason": "too expensive"},
                cookies=auth_cookies,
            )
        assert res.json()["status"] == "researching"

    # Reject attempt 3 (the 3rd rejection) -> this research call must hit the cap.
    flight_option = next(c for c in client.get(f"/trips/{session_id}", cookies=auth_cookies).json()["categories"] if c["name"] == "flight")[
        "options"
    ][0]
    client.post(
        f"/trips/{session_id}/options/{flight_option['option_id']}/decision",
        json={"decision": "rejected"},
        cookies=auth_cookies,
    )
    with patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f5", "price": 999}])) as mock_search:
        fallback_res = client.post(
            f"/trips/{session_id}/categories/flight/research",
            json={"reason": "give up"},
            cookies=auth_cookies,
        )
    assert fallback_res.json()["status"] == "manual_fallback"
    mock_search.assert_not_called()

    # The accommodation category was never touched by any of this.
    final_state = client.get(f"/trips/{session_id}", cookies=auth_cookies).json()
    final_accommodation = next(c for c in final_state["categories"] if c["name"] == "accommodation")
    assert final_accommodation["options"][0]["option_id"] == accommodation_option["option_id"]
    assert final_accommodation["status"] == "selecting"
