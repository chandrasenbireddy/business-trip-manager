"""Orchestrator agent: NL intake, calendar-availability check, hands off to Planner.

FR-001/FR-002: parse an English-only trip request, extract structured fields,
ask at most one clarifying question if something essential is missing.
FR-015: read-only calendar-availability check before research begins
(added during /speckit-analyze, finding C1).
"""

import asyncio
import json
import logging
from datetime import date

from openai import AsyncOpenAI

from agents.base import traced
from agents.models.cost import record_cost_event
from agents.models.session import create_session, get_session, update_session_status, update_trip_request
from tools import events
from tools.db_context import tenant_connection
from tools.model_router import call_with_fallback, client_config, primary_model

MISSING_ORIGIN_QUESTION = "Where will you be flying from?"
logger = logging.getLogger(__name__)
_research_tasks: set[asyncio.Task] = set()

REQUIRED_FIELDS = ("destination", "start_date", "end_date")

_EXTRACTION_FIELDS = ("destination", "start_date", "end_date", "purpose", "budget", "reference_point", "origin")

_EXTRACTION_SYSTEM_PROMPT = """You extract structured trip details from a traveler's free-text request.

Respond with ONLY a JSON object (no prose, no markdown fences) with exactly these fields:
- destination: string, the city/place being traveled to. Required — use "" if genuinely absent.
- start_date: string, ISO 8601 date (YYYY-MM-DD), or null if not stated.
- end_date: string, ISO 8601 date (YYYY-MM-DD), or null if not stated.
- purpose: string or null, the stated reason for travel.
- budget: number or null, the traveler's total stated budget in USD (strip currency symbols).
- reference_point: string or null, a named landmark/area the traveler wants to stay near.
- origin: string or null, the departure city — only if explicitly stated.

Dates with no year stated are ambiguous — resolve to the next future occurrence of that
month/day relative to today, {today}. Never invent a value not present in the request.
"""


async def _extract_trip_details(description: str) -> dict:
    """LLM-backed extraction of {destination, start_date, end_date, purpose,
    budget, reference_point, origin} from a free-text English request.
    Broken out as its own function so tests can patch it without a live
    model call.

    strands.Agent has no extract_structured method (that was never a real
    Strands SDK method — found via the AttributeError it raised on every
    real call). Calls NVIDIA NIM directly instead, via the OpenAI-compatible
    chat completions API both NIM and Groq (call_with_fallback's retry
    target) implement — tools/model_router.py's client_config() already
    resolves the right base_url/api_key/model for whichever of the two this
    is currently calling.
    """

    async def _invoke(model_id: str) -> dict:
        which = "primary" if model_id == primary_model("orchestrator") else "fallback"
        cfg = client_config("orchestrator", which=which)
        client = AsyncOpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])
        response = await client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT.format(today=date.today().isoformat())},
                {"role": "user", "content": description},
            ],
            response_format={"type": "json_object"},
        )
        return _parse_extraction(response.choices[0].message.content)

    return await call_with_fallback("orchestrator", _invoke)


def _parse_extraction(content: str) -> dict:
    """Some NIM-hosted models wrap JSON in a markdown fence despite
    response_format={"type": "json_object"} — strip one if present. Keeps
    only the fields this codebase actually reads, dropping anything extra
    the model adds unprompted; a malformed/non-JSON response raises, which
    call_with_fallback treats the same as any other primary-model failure.
    """
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[len("json") :]
    parsed = json.loads(text)
    return {field: parsed.get(field) for field in _EXTRACTION_FIELDS}


def _missing_required_field(details: dict) -> str | None:
    for field_name in REQUIRED_FIELDS:
        if not details.get(field_name):
            return field_name
    return None


async def _get_home_city_preference(tenant_id: str, user_id: str) -> str | None:
    from agents.memory import get_preferences

    preferences = (await get_preferences(tenant_id, user_id))["preferences"]
    for pref in preferences:
        if pref["type"] == "home_city":
            return pref["value"].get("city")
    return None


async def _dispatch_research(session, tenant_id: str, user_id: str, details: dict) -> None:
    """Everything that happens once destination/dates/origin are all known —
    shared between the normal path (origin present or a home_city preference
    covered it) and handle_clarification_answer (origin was just supplied).
    """
    # spec FR-021/FR-023: attribute the NL-extraction call's cost to this
    # session. tokens/cost are 0 until a real model call replaces
    # _extract_trip_details's stub — the recording pipeline itself is real.
    await record_cost_event(
        tenant_id,
        session.session_id,
        user_id,
        agent_type="orchestrator",
        model_id=primary_model("orchestrator"),
    )

    from agents.memory import check_date_conflict, get_airbnb_context

    conflicts = await check_calendar_availability(
        user_id,
        details["start_date"],
        details["end_date"],
        calendar_credentials_ref=f"{user_id}/google_calendar_token",
    )
    if conflicts:
        await events.publish(session.session_id, "calendar_conflict", {"conflicts": conflicts})

    # spec FR-026/FR-027: called at session start (contracts/agent-tools.md,
    # AR-07) — cookie_expired degrades to anonymous search, never blocking.
    airbnb_context = await get_airbnb_context(user_id)
    reservation_conflicts = check_date_conflict(airbnb_context["upcoming_reservations"], details["start_date"], details["end_date"])
    if reservation_conflicts:
        await events.publish(session.session_id, "airbnb_conflict", {"reservations": reservation_conflicts})

    from agents.planner import run_research

    await run_research(session.session_id, tenant_id, user_id, details, airbnb_context)


async def _run_research_background(session, tenant_id: str, user_id: str, details: dict) -> None:
    try:
        await _dispatch_research(session, tenant_id, user_id, details)
    except Exception as exc:  # noqa: BLE001 — the session must record every research failure
        logger.error(
            "background research failed session_id=%s error_type=%s",
            session.session_id,
            type(exc).__name__,
        )
        await update_session_status(tenant_id, session.session_id, "research_failed")
        await events.publish(
            session.session_id,
            "research_failed",
            {"status": "research_failed", "error_type": type(exc).__name__},
        )


def _schedule_research(session, tenant_id: str, user_id: str, details: dict) -> None:
    task = asyncio.create_task(_run_research_background(session, tenant_id, user_id, details))
    _research_tasks.add(task)
    task.add_done_callback(_research_tasks.discard)


@traced("orchestrator.handle_trip_request")
async def handle_trip_request(description: str, user_id: str, tenant_id: str) -> dict:
    details = await _extract_trip_details(description)

    missing = _missing_required_field(details)
    if missing:
        # At most one clarifying question (spec FR-002) — never a multi-question form.
        return {"clarifying_question": f"What {missing.replace('_', ' ')} did you have in mind?"}

    if not details.get("origin"):
        details["origin"] = await _get_home_city_preference(tenant_id, user_id)

    from agents.memory import store_turn

    # One transaction: a session whose opening turn failed to store would be
    # left stuck in_progress with no turn and no research ever dispatched.
    async with tenant_connection(tenant_id) as conn:
        session = await create_session(tenant_id, user_id, trip_request=details, conn=conn)
        await store_turn(tenant_id, session.session_id, user_id, role="traveler", content=description, conn=conn)

    if not details["origin"]:
        # Fix: trip intake flow — origin wasn't stated and no home_city
        # preference covers it. Pause here (session already exists, so the
        # traveler's opening message is recorded either way) rather than
        # guess a departure city; POST /trips/{id}/clarify resumes exactly
        # where this leaves off once answered.
        await update_session_status(tenant_id, session.session_id, "awaiting_clarification")
        return {"clarifying_question": MISSING_ORIGIN_QUESTION, "session_id": session.session_id}

    _schedule_research(session, tenant_id, user_id, details)

    return {"session_id": session.session_id, "status": "in_progress"}


@traced("orchestrator.handle_clarification_answer")
async def handle_clarification_answer(tenant_id: str, session_id: str, answer: str) -> dict:
    """Resumes a session paused by handle_trip_request's missing-origin
    clarifying question. Stores the answer as a durable home_city
    preference (spec: fix trip intake flow) so this traveler is never asked
    again, then proceeds exactly as if origin had been in the original
    request.
    """
    session = await get_session(tenant_id, session_id)

    from agents.memory import store_preference

    await store_preference(tenant_id, session.user_id, "home_city", {"city": answer})

    details = dict(session.trip_request or {})
    details["origin"] = answer
    await update_trip_request(tenant_id, session_id, details)
    await update_session_status(tenant_id, session_id, "in_progress")

    _schedule_research(session, tenant_id, session.user_id, details)

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
