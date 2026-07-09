"""Integration test: cost summary shown at session end; itinerary report
generated, downloadable, and shareable via link (spec Story 6).

T088 — written before the Story 6 implementation tasks (T089-T095) exist;
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


def test_full_trip_produces_cost_summary_and_shareable_report(client, auth_cookies):
    with (
        patch("agents.orchestrator._extract_trip_details", AsyncMock(return_value=RIYADH_DETAILS)),
        patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f1", "price": 400}])),
        patch("agents.planner.search_airbnb", AsyncMock(return_value=[{"id": "a1", "price": 600}])),
        patch("agents.booking.add_to_calendar", AsyncMock(return_value={"status": "ok"})),
        patch("agents.booking.send_email", AsyncMock(return_value={"status": "ok"})),
    ):
        created = client.post("/trips", json={"description": "3 nights in Riyadh"}, cookies=auth_cookies).json()
        session_id = created["session_id"]

        state = client.get(f"/trips/{session_id}", cookies=auth_cookies).json()
        for category in state["categories"]:
            option_id = category["options"][0]["option_id"]
            client.post(
                f"/trips/{session_id}/options/{option_id}/decision",
                json={"decision": "selected"},
                cookies=auth_cookies,
            )
        client.post(f"/trips/{session_id}/confirm", json={}, cookies=auth_cookies)

    # spec FR-023: presented "before they leave" — broken down by activity,
    # not a single opaque number, and every activity that ran shows up.
    cost_res = client.get(f"/trips/{session_id}/cost-summary", cookies=auth_cookies)
    assert cost_res.status_code == 200
    by_activity = cost_res.json()["by_activity"]
    assert {
        "orchestrator",
        "planner",
        "scraper_flights",
        "scraper_airbnb",
        "memory",
        "booking",
    } <= set(by_activity.keys())

    # spec FR-024/025: self-contained document, downloadable, and (here, since
    # the upload succeeds) also shareable via a link with an expiry.
    with patch("tools.report._upload_to_gcs", AsyncMock(return_value="https://btm.ai/trips/abc123")):
        report_res = client.get(f"/trips/{session_id}/report", cookies=auth_cookies)
    assert report_res.status_code == 200
    body = report_res.json()
    assert body["share_url"] == "https://btm.ai/trips/abc123"
    assert body["share_expires_at"] is not None

    download_res = client.get(body["download_url"], cookies=auth_cookies)
    assert download_res.status_code == 200
    assert "Riyadh" in download_res.text
    assert "Cost breakdown" in download_res.text
