"""Orchestrator agent: NL intake, calendar-availability check, hands off to Planner.

FR-001/FR-002: parse an English-only trip request, extract structured fields,
ask at most one clarifying question if something essential is missing.
FR-015: read-only calendar-availability check before research begins
(added during /speckit-analyze, finding C1).
"""

from agents.base import BtmAgent, traced
from agents.models.session import create_session
from tools import events
from tools.model_router import call_with_fallback

REQUIRED_FIELDS = ("destination", "start_date", "end_date")

_orchestrator = BtmAgent()


async def _extract_trip_details(description: str) -> dict:
    """LLM-backed extraction of {destination, start_date, end_date, purpose,
    budget, constraints[]} from a free-text English request. Broken out as its
    own function so tests can patch it without a live model call.
    """

    async def _invoke(model_id: str) -> dict:
        return await _orchestrator.extract_structured(  # provided by strands.Agent
            model=model_id,
            prompt=description,
            schema={
                "destination": "string",
                "start_date": "date|null",
                "end_date": "date|null",
                "purpose": "string|null",
                "budget": "number|null",
                "constraints": "string[]",
            },
        )

    return await call_with_fallback("orchestrator", _invoke)


def _missing_required_field(details: dict) -> str | None:
    for field_name in REQUIRED_FIELDS:
        if not details.get(field_name):
            return field_name
    return None


@traced("orchestrator.handle_trip_request")
async def handle_trip_request(description: str, user_id: str, tenant_id: str) -> dict:
    details = await _extract_trip_details(description)

    missing = _missing_required_field(details)
    if missing:
        # At most one clarifying question (spec FR-002) — never a multi-question form.
        return {"clarifying_question": f"What {missing.replace('_', ' ')} did you have in mind?"}

    session = await create_session(tenant_id, user_id, trip_request=details)

    from agents.memory import store_turn

    await store_turn(tenant_id, session.session_id, user_id, role="traveler", content=description)

    conflicts = await check_calendar_availability(
        user_id, details["start_date"], details["end_date"], calendar_credentials_ref=f"{user_id}/google_calendar_token"
    )
    if conflicts:
        await events.publish(session.session_id, "calendar_conflict", {"conflicts": conflicts})

    from agents.planner import run_research

    await run_research(session.session_id, tenant_id, user_id, details)

    return {"session_id": session.session_id, "status": "in_progress"}


@traced("orchestrator.check_calendar_availability")
async def check_calendar_availability(user_id: str, start_date: str, end_date: str, calendar_credentials_ref: str) -> list[dict]:
    """Read-only calendar check against the requested dates, run once dates are
    known and before research dispatch (spec FR-015). A non-empty return
    surfaces a `calendar_conflict` SSE event (contracts/bff-api.md).

    No connected calendar (credential not found) is not an error — the trip
    request proceeds without a conflict check, same non-blocking spirit as
    the Airbnb account's graceful degradation (constitution Principle XI).
    """
    from tools import secrets

    try:
        token = secrets.resolve(calendar_credentials_ref)
    except Exception:
        return []
    return await _fetch_calendar_conflicts(token, start_date, end_date)


async def _fetch_calendar_conflicts(access_token: str, start_date: str, end_date: str) -> list[dict]:
    # Real implementation calls the Google/Microsoft Calendar freebusy API here.
    # ponytail: stubbed pending a live OAuth token in an actual deployment —
    # upgrade when calendar.readonly scope is exercised end to end.
    return []
