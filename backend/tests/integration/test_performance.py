"""T112 — performance validation against NFR-01/spec FR-004: research < 90s,
card load < 500ms, booking execution < 60s.

Honest scope: scrapers and OAuth-backed tools are mocked (no live browser-use,
LLM, or Google API calls in this sandbox), so these numbers measure the
harness's own orchestration/DB overhead, not real external latency. They
confirm the implementation adds no unexpected internal bottleneck relative to
the budget — they do not substitute for a real staging-environment timing run
once live scraper/model infra exists.
"""

import time
from unittest.mock import AsyncMock, patch

TRIP_REQUEST = "I need to go to Riyadh July 14-17, budget $1500, near KAFD"


def test_research_card_load_and_booking_complete_within_nfr_01_budgets(client, auth_cookies):
    with (
        patch(
            "agents.orchestrator._extract_trip_details",
            AsyncMock(
                return_value={
                    "destination": "Riyadh",
                    "start_date": "2026-07-14",
                    "end_date": "2026-07-17",
                    "purpose": "kickoff",
                    "budget": 1500,
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
        research_start = time.monotonic()
        created = client.post("/trips", json={"description": TRIP_REQUEST}, cookies=auth_cookies).json()
        session_id = created["session_id"]
        research_elapsed = time.monotonic() - research_start
        assert research_elapsed < 90, f"research took {research_elapsed:.2f}s, budget is 90s (FR-004)"

        card_load_start = time.monotonic()
        state = client.get(f"/trips/{session_id}", cookies=auth_cookies).json()
        card_load_elapsed = time.monotonic() - card_load_start
        assert card_load_elapsed < 0.5, f"card load took {card_load_elapsed * 1000:.0f}ms, budget is 500ms (NFR-01)"
        assert {c["name"] for c in state["categories"]} == {"flight", "accommodation"}

        for category in state["categories"]:
            option_id = category["options"][0]["option_id"]
            client.post(
                f"/trips/{session_id}/options/{option_id}/decision",
                json={"decision": "selected"},
                cookies=auth_cookies,
            )

        booking_start = time.monotonic()
        confirm_res = client.post(f"/trips/{session_id}/confirm", json={}, cookies=auth_cookies)
        booking_elapsed = time.monotonic() - booking_start
        assert confirm_res.status_code == 200
        assert booking_elapsed < 60, f"booking took {booking_elapsed:.2f}s, budget is 60s (NFR-01)"
