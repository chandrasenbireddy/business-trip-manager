"""ShareableItineraryReport model + generator (data-model.md; spec FR-024/FR-025).

The self-contained HTML is regenerated on demand from the session's own data
rather than fetched from storage — that's what makes "download always
succeeds even if the hosted-link upload fails" (FR-025) trivially true: the
download path never depends on a blob existing anywhere.
"""

import html
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from agents.models.cost import get_session_cost_summary
from agents.models.session import get_options, get_session
from tools.db_context import tenant_connection

LINK_EXPIRY_DAYS = 30


@dataclass
class ShareableItineraryReport:
    report_id: str
    session_id: str
    tenant_id: str
    html_ref: str | None
    link_url: str | None
    link_expires_at: datetime | None
    download_available: bool = True


def generate_report_html(session, options: list, cost_summary: dict) -> str:
    """Self-contained: opens standalone, no login, no network required (FR-024)."""
    trip_request = session.trip_request or {}
    selected = [o for o in options if o.decision == "selected"]

    rows = "".join(
        f"<tr><td>{html.escape(o.category)}</td><td>{html.escape(str(o.attributes))}</td></tr>" for o in selected
    )
    cost_rows = "".join(
        f"<tr><td>{html.escape(activity)}</td><td>${amount:.4f}</td></tr>"
        for activity, amount in cost_summary["by_activity"].items()
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Trip to {html.escape(str(trip_request.get("destination", "")))}</title></head>
<body>
<h1>Trip to {html.escape(str(trip_request.get("destination", "")))}</h1>
<p>{html.escape(str(trip_request.get("start_date", "")))} &ndash; {html.escape(str(trip_request.get("end_date", "")))}</p>
<h2>Itinerary</h2>
<table>{rows}</table>
<h2>Cost breakdown (including this session's own AI cost)</h2>
<table>{cost_rows}</table>
<p>Total: ${cost_summary["total"] + session.total_cost_usd:.4f}</p>
</body></html>"""


async def _upload_to_gcs(report_id: str, html_content: str) -> str | None:
    # Real implementation uploads to a GCS bucket and returns its public URL.
    # ponytail: no bucket configured yet — always falls back to download-only,
    # exactly the path FR-025 requires to always work regardless.
    return None


async def get_or_create_report(tenant_id: str, session_id: str) -> dict:
    session = await get_session(tenant_id, session_id)
    options = await get_options(tenant_id, session_id)
    cost_summary = await get_session_cost_summary(tenant_id, session_id)
    report_html = generate_report_html(session, options, cost_summary)

    report_id = str(uuid.uuid4())
    link_url = await _upload_to_gcs(report_id, report_html)
    link_expires_at = datetime.now(timezone.utc) + timedelta(days=LINK_EXPIRY_DAYS) if link_url else None

    async with tenant_connection(tenant_id) as conn:
        await conn.execute(
            "INSERT INTO shareable_itinerary_reports (report_id, session_id, tenant_id, link_url, link_expires_at) "
            "VALUES ($1, $2, $3, $4, $5)",
            report_id,
            session_id,
            tenant_id,
            link_url,
            link_expires_at,
        )

    return {
        "download_url": f"/trips/{session_id}/report/download",
        "share_url": link_url,
        "share_expires_at": link_expires_at.isoformat() if link_expires_at else None,
        "_html": report_html,  # BFF route serves this directly; not part of the public contract shape
    }
