"""Integration test: date-conflict warning, wishlist/past-stay ranking and
badges, non-blocking reconnect prompt on expiry (spec Story 5).

T079 — written before the Story 5 implementation tasks (T080-T086) exist;
MUST fail until then.

httpx's ASGITransport (both the sync TestClient and an AsyncClient use it
against an in-process app) fully buffers the app call before returning
anything — see tests/contract/test_bff_stream.py's module docstring. So the
SSE-reading test here drives the session all the way to `booking_complete`
(which ends the stream server-side) before opening it.
"""

import json
from unittest.mock import AsyncMock, patch

RIYADH_DETAILS = {
    "destination": "Riyadh",
    "start_date": "2026-11-10",
    "end_date": "2026-11-13",
    "purpose": "conference",
    "budget": 1200,
    "constraints": [],
}


def _read_full_stream(client, session_id, cookies):
    events = []
    event_name = None
    with client.stream("GET", f"/trips/{session_id}/stream", cookies=cookies) as res:
        assert res.status_code == 200
        for line in res.iter_lines():
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
            elif line.startswith("data:") and event_name:
                events.append((event_name, json.loads(line.removeprefix("data:").strip())))
                event_name = None
    return events


def test_connected_account_surfaces_conflict_and_ranks_badges(client, auth_cookies):
    airbnb_context = {
        "connected": True,
        "cookie_status": "valid",
        "upcoming_reservations": [
            {
                "listing_id": "existing",
                "dates": {"checkin": "2026-11-11", "checkout": "2026-11-12"},
                "address": "Riyadh",
                "confirmation_code": "ABC123",
            }
        ],
        "past_stays": [{"listing_id": "stayed", "destination": "Riyadh"}],
        "wishlist": [{"listing_id": "saved"}],
    }

    with (
        patch("agents.orchestrator._extract_trip_details", AsyncMock(return_value=RIYADH_DETAILS)),
        patch("agents.memory.get_airbnb_context", AsyncMock(return_value=airbnb_context)),
        patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f1", "price": 400}])),
        patch(
            "agents.planner.search_airbnb",
            AsyncMock(
                return_value=[
                    {"id": "new", "price": 500},
                    {"id": "saved", "price": 600},
                    {"id": "stayed", "price": 550},
                ]
            ),
        ),
    ):
        created = client.post("/trips", json={"description": "3 nights in Riyadh"}, cookies=auth_cookies).json()
    session_id = created["session_id"]

    # spec FR-028: wishlist first, past stay second, new third — with badges.
    state = client.get(f"/trips/{session_id}", cookies=auth_cookies).json()
    accommodation = next(c for c in state["categories"] if c["name"] == "accommodation")["options"]
    ordered_ids = [o["attributes"]["id"] for o in accommodation]
    assert ordered_ids == ["saved", "stayed", "new"]
    assert accommodation[0]["badge"] == "wishlisted"
    assert accommodation[1]["badge"] == "past_stay"
    assert accommodation[2]["badge"] is None

    # Drive to booking_complete (the stream never yields anything to a reader
    # until the app call itself finishes — see module docstring) then confirm
    # spec FR-027's conflict event was on the stream.
    flight_option = next(c for c in state["categories"] if c["name"] == "flight")["options"][0]
    for option in [flight_option, accommodation[0]]:
        client.post(
            f"/trips/{session_id}/options/{option['option_id']}/decision",
            json={"decision": "selected"},
            cookies=auth_cookies,
        )
    with (
        patch("agents.booking.add_to_calendar", AsyncMock(return_value={"status": "ok"})),
        patch("agents.booking.send_email", AsyncMock(return_value={"status": "ok"})),
    ):
        client.post(f"/trips/{session_id}/confirm", json={}, cookies=auth_cookies)

    events = _read_full_stream(client, session_id, auth_cookies)
    conflict_events = [data for name, data in events if name == "airbnb_conflict"]
    assert len(conflict_events) == 1
    assert conflict_events[0]["reservations"][0]["listing_id"] == "existing"


def test_expired_account_degrades_without_blocking_and_status_reflects_it(client, auth_cookies):
    with (
        patch("agents.orchestrator._extract_trip_details", AsyncMock(return_value=RIYADH_DETAILS)),
        patch("agents.memory.fetch_airbnb_account", AsyncMock(return_value={"status": "cookie_expired"})),
        patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f1", "price": 400}])),
        patch("agents.planner.search_airbnb", AsyncMock(return_value=[{"id": "a1", "price": 600}])),
    ):
        created = client.post("/trips", json={"description": "3 nights in Riyadh"}, cookies=auth_cookies)

    # spec FR-029: never fails or blocks the trip request.
    assert created.status_code == 200
    assert created.json()["session_id"] is not None

    with patch("agents.memory.fetch_airbnb_account", AsyncMock(return_value={"status": "cookie_expired"})):
        status_res = client.get("/users/me/airbnb-status", cookies=auth_cookies)
    assert status_res.status_code == 200
    assert status_res.json()["cookie_status"] == "expired"
