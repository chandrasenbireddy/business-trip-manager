"""Full trip flow, end to end: NL request -> research -> swipe -> confirm ->
booking -> calendar/email. Uses the PRD's own worked example (quickstart.md,
spec.md Story 1 acceptance scenarios) so behavior is directly comparable to
the spec.

T029 — written before the Story 1 implementation tasks (T030-T042) exist;
MUST fail until then. Scrapers and OAuth-backed tools are mocked; this test
exercises the orchestration/state-machine logic, not real browser-use/GCP.
"""

from unittest.mock import AsyncMock, patch

TRIP_REQUEST = "I need to go to Riyadh July 14-17 for the HUMAIN kickoff, budget around $1500 total, need to be near KAFD"


def test_full_trip_flow_riyadh_kafd_example(client, auth_cookies):
    with (
        patch(
            "agents.orchestrator._extract_trip_details",
            AsyncMock(
                return_value={
                    "destination": "Riyadh",
                    "start_date": "2026-07-14",
                    "end_date": "2026-07-17",
                    "purpose": "HUMAIN kickoff",
                    "budget": 1500,
                    "origin": "Dammam",
                    "constraints": ["near KAFD"],
                }
            ),
        ),
        patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f1", "price": 400}])),
        patch(
            "agents.planner.search_airbnb",
            AsyncMock(return_value=[{"id": "a1", "price": 600, "distance_km": 1.2}]),
        ),
        patch("agents.booking.add_to_calendar", AsyncMock(return_value={"status": "ok"})),
        patch("agents.booking.send_email", AsyncMock(return_value={"status": "ok"})),
    ):
        created = client.post("/trips", json={"description": TRIP_REQUEST}, cookies=auth_cookies).json()
        session_id = created["session_id"]

        # Research completes and both categories offer at least one card (FR-005/006).
        state = client.get(f"/trips/{session_id}", cookies=auth_cookies).json()
        assert {c["name"] for c in state["categories"]} == {"flight", "accommodation"}

        # Swipe: select the one option in each category.
        flight_option = state["categories"][0]["options"][0]["option_id"]
        accom_option = state["categories"][1]["options"][0]["option_id"]
        for option_id in (flight_option, accom_option):
            res = client.post(
                f"/trips/{session_id}/options/{option_id}/decision",
                json={"decision": "selected"},
                cookies=auth_cookies,
            )
            assert res.status_code == 200

        # Confirm the itinerary (FR-009/010) — this is the only point booking may start.
        confirm_res = client.post(f"/trips/{session_id}/confirm", json={}, cookies=auth_cookies)
        assert confirm_res.status_code == 200
        assert confirm_res.json()["status"] == "booking"

        final_state = client.get(f"/trips/{session_id}", cookies=auth_cookies).json()
        assert final_state["status"] == "confirmed"
        assert "itinerary" in final_state
