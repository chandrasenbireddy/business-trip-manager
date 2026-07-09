"""Contract test for GET /trips/{id}/cost-summary and GET /trips/{id}/report
(contracts/bff-api.md, spec FR-025).

T087 — written before these endpoints exist (T093); MUST fail until then.
The download path MUST always succeed even if link upload fails.
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


def _create_trip(client, cookies):
    with (
        patch("agents.orchestrator._extract_trip_details", AsyncMock(return_value=RIYADH_DETAILS)),
        patch("agents.planner.search_flights", AsyncMock(return_value=[{"id": "f1", "price": 400}])),
        patch("agents.planner.search_airbnb", AsyncMock(return_value=[{"id": "a1", "price": 600}])),
    ):
        return client.post("/trips", json={"description": "3 nights in Riyadh"}, cookies=cookies).json()


def test_cost_summary_returns_by_activity_breakdown(client, auth_cookies):
    created = _create_trip(client, auth_cookies)
    res = client.get(f"/trips/{created['session_id']}/cost-summary", cookies=auth_cookies)
    assert res.status_code == 200
    body = res.json()
    assert "by_activity" in body
    assert "total" in body


def test_report_download_always_succeeds_even_when_link_upload_fails(client, auth_cookies):
    created = _create_trip(client, auth_cookies)
    session_id = created["session_id"]

    with patch("tools.report._upload_to_gcs", AsyncMock(return_value=None)):
        report_res = client.get(f"/trips/{session_id}/report", cookies=auth_cookies)
    assert report_res.status_code == 200
    body = report_res.json()
    assert body["share_url"] is None
    assert body["download_url"] == f"/trips/{session_id}/report/download"

    download_res = client.get(body["download_url"], cookies=auth_cookies)
    assert download_res.status_code == 200
    assert "text/html" in download_res.headers["content-type"]
    assert "Riyadh" in download_res.text
