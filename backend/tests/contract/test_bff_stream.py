"""Contract test for GET /trips/{id}/stream SSE payloads (contracts/bff-api.md).

T026 — written before api/routes/trips.py's SSE relay exists (T037); MUST fail
until then. Asserts the event-name/payload shapes the frontend's useTripStream
hook depends on, including `calendar_conflict` (finding C1 from /speckit-analyze).

httpx's ASGITransport (which both the sync TestClient and an AsyncClient use
against an in-process app) fully buffers the app call before returning
anything — it cannot deliver a genuinely never-ending stream incrementally.
So these tests drive the session all the way to `booking_complete` (which
ends the stream server-side, tools/events.py) BEFORE opening the SSE
endpoint, then read the now-complete, fully-buffered event log.
"""

import json
from contextlib import ExitStack
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

EXPECTED_EVENT_NAMES = {
    "calendar_conflict",
    "research_started",
    "card_ready",
    "category_complete",
    "researching_again",
    "manual_fallback",
    "itinerary_ready",
    "pending_approval",
    "booking_progress",
    "booking_complete",
    "degraded",
    "error",
}


def _run_to_booking_complete(client, cookies, description, extra_patches=()):
    with ExitStack() as stack:
        stack.enter_context(patch("agents.orchestrator._extract_trip_details", AsyncMock(return_value=RIYADH_DETAILS)))
        stack.enter_context(
            patch(
                "agents.planner.search_flights",
                AsyncMock(return_value=[{"id": "f1", "price": 400}]),
            )
        )
        stack.enter_context(
            patch(
                "agents.planner.search_airbnb",
                AsyncMock(return_value=[{"id": "a1", "price": 600, "distance_km": 1.2}]),
            )
        )
        stack.enter_context(patch("agents.booking.add_to_calendar", AsyncMock(return_value={"status": "ok"})))
        stack.enter_context(patch("agents.booking.send_email", AsyncMock(return_value={"status": "ok"})))
        for p in extra_patches:
            stack.enter_context(p)

        created = client.post("/trips", json={"description": description}, cookies=cookies).json()
        session_id = created["session_id"]

        state = client.get(f"/trips/{session_id}", cookies=cookies).json()
        for category in state["categories"]:
            option_id = category["options"][0]["option_id"]
            client.post(
                f"/trips/{session_id}/options/{option_id}/decision",
                json={"decision": "selected"},
                cookies=cookies,
            )

        client.post(f"/trips/{session_id}/confirm", json={}, cookies=cookies)

    return session_id


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


def test_stream_emits_only_contracted_event_names(client, auth_cookies):
    session_id = _run_to_booking_complete(client, auth_cookies, "3 nights in Riyadh near KAFD")
    events = _read_full_stream(client, session_id, auth_cookies)

    seen = {name for name, _ in events}
    for name in seen:
        assert name in EXPECTED_EVENT_NAMES, f"undocumented SSE event: {name}"
    assert {"research_started", "card_ready", "itinerary_ready", "booking_complete"} <= seen


def test_calendar_conflict_event_shape(client, auth_cookies):
    session_id = _run_to_booking_complete(
        client,
        auth_cookies,
        "3 nights in Riyadh near KAFD, Nov 10-13",
        extra_patches=(
            patch(
                "agents.orchestrator._fetch_calendar_conflicts",
                AsyncMock(
                    return_value=[
                        {
                            "event_title": "Board sync",
                            "start": "2026-11-11T09:00:00Z",
                            "end": "2026-11-11T10:00:00Z",
                        }
                    ]
                ),
            ),
            patch("tools.secrets.resolve", lambda ref: "fake-token"),
        ),
    )
    events = _read_full_stream(client, session_id, auth_cookies)

    conflict_data = next(data for name, data in events if name == "calendar_conflict")
    assert "conflicts" in conflict_data
    assert all({"event_title", "start", "end"} <= c.keys() for c in conflict_data["conflicts"])
