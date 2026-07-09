"""Integration test: out-of-policy options are filtered before cards are shown,
and an above-threshold itinerary pauses for approval instead of booking
(spec Story 4).

T067 — written before the Story 4 implementation tasks (T068-T077) exist;
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


def test_out_of_policy_options_filtered_and_above_threshold_pauses_for_approval(client, admin_cookies, auth_cookies):
    # Admin sets a policy: max flight budget below one of the two options
    # the mocked search will return, and an approval threshold the selected
    # itinerary will exceed.
    # set_policy merges into whatever's already there (by design — editing one
    # field shouldn't clobber others a prior test set), so this must set every
    # field the assertions below depend on, not just the two new ones — a
    # leftover approved_airlines from an earlier test run would otherwise
    # filter every mocked option here (they carry no "airline" field at all).
    policy_res = client.put(
        "/admin/policy",
        json={"max_flight_budget": 300, "approval_threshold": 500, "approved_airlines": []},
        cookies=admin_cookies,
    )
    assert policy_res.status_code == 200

    with (
        patch("agents.orchestrator._extract_trip_details", AsyncMock(return_value=RIYADH_DETAILS)),
        patch(
            "agents.planner.search_flights",
            AsyncMock(return_value=[{"id": "cheap", "price": 250}, {"id": "expensive", "price": 400}]),
        ),
        patch(
            "agents.planner.search_airbnb",
            AsyncMock(return_value=[{"id": "a1", "price": 600, "distance_km": 1.2}]),
        ),
    ):
        created = client.post("/trips", json={"description": "3 nights in Riyadh"}, cookies=auth_cookies).json()
    session_id = created["session_id"]

    # spec FR-018: the $400 flight never appears — filtered before any card_ready.
    state = client.get(f"/trips/{session_id}", cookies=auth_cookies).json()
    flight_category = next(c for c in state["categories"] if c["name"] == "flight")
    flight_prices = {o["attributes"]["price"] for o in flight_category["options"]}
    assert flight_prices == {250}

    # Select the compliant flight + the accommodation — total (250 + 600 = 850) exceeds
    # the 500 threshold.
    for opt in flight_category["options"] + next(c for c in state["categories"] if c["name"] == "accommodation")["options"]:
        client.post(
            f"/trips/{session_id}/options/{opt['option_id']}/decision",
            json={"decision": "selected"},
            cookies=auth_cookies,
        )

    with patch("agents.booking.execute_booking", AsyncMock()) as mock_execute:
        confirm_res = client.post(f"/trips/{session_id}/confirm", json={}, cookies=auth_cookies)

    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "pending_approval"
    mock_execute.assert_not_called()

    final_state = client.get(f"/trips/{session_id}", cookies=auth_cookies).json()
    assert final_state["status"] == "pending_approval"
