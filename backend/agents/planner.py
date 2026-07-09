"""Planner agent: parallel research dispatch, results merge, itinerary assembly,
category re-search recovery.

spec FR-003 (parallel dispatch), FR-005/FR-006 (card_ready/category_complete),
FR-007/FR-008/FR-008a (re-search, reject cap, zero-result retry), FR-009
(build_itinerary).
"""

import asyncio

from agents.base import traced
from agents.models.session import (
    add_research_options,
    get_max_attempt_number,
    get_options,
    get_session,
    record_decision,
    set_itinerary,
    update_session_status,
)
from scrapers.airbnb import search_airbnb
from scrapers.flights import search_flights
from tools import events

CATEGORIES = ("flight", "accommodation")
REJECT_CAP = 3
_PREFERENCE_TYPES_BY_CATEGORY = {
    "flight": ("seat", "preferred_airline", "budget_pattern"),
    "accommodation": ("hotel_proximity", "dietary", "budget_pattern"),
}


def _preference_notes(preferences: list[dict], category: str) -> str:
    relevant = [p for p in preferences if p["type"] in _PREFERENCE_TYPES_BY_CATEGORY.get(category, ())]
    return "; ".join(f"{p['type']}={p['value']}" for p in relevant)


def _history_notes(relevant_history: list[dict]) -> str:
    if not relevant_history:
        return ""
    return f"Traveler has visited this destination before ({len(relevant_history)} prior trip(s)) — factor that in."


async def _search_category(category: str, trip_request: dict, notes: str = "", broaden: bool = False) -> list[dict]:
    if category == "flight":
        return await search_flights(
            origin=trip_request.get("origin", ""),
            destination=trip_request["destination"],
            depart_date=trip_request["start_date"],
            return_date=trip_request.get("end_date"),
            notes=notes,
            broaden=broaden,
        )
    return await search_airbnb(
        destination=trip_request["destination"],
        reference_point=trip_request.get("reference_point", {"lat": 0.0, "lng": 0.0}),
        checkin=trip_request["start_date"],
        checkout=trip_request["end_date"],
        notes=notes,
        broaden=broaden,
    )


async def _search_with_broaden_retry(category: str, trip_request: dict, notes: str = "") -> list[dict]:
    """spec FR-008a: a zero-result category gets one silent, broadened retry
    before it's ever shown empty — this retry does NOT consume the reject
    cap (it happens before any batch is persisted with an attempt_number).
    """
    results = await _search_category(category, trip_request, notes=notes)
    if not results:
        results = await _search_category(category, trip_request, notes=notes, broaden=True)
    return results


@traced("planner.run_research")
async def run_research(session_id: str, tenant_id: str, user_id: str, trip_request: dict) -> None:
    """spec Story 3 (FR-013/FR-014): preferences and destination history are
    read before first-pass research, so results already reflect them without
    the traveler restating anything (wired here per tasks.md T062).
    """
    from agents.memory import get_preferences, retrieve_context

    preferences = (await get_preferences(tenant_id, user_id))["preferences"]
    history = (await retrieve_context(tenant_id, user_id, destination=trip_request.get("destination")))[
        "relevant_history"
    ]

    await events.publish(session_id, "research_started", {"categories": list(CATEGORIES)})

    flight_results, accommodation_results = await asyncio.gather(
        _search_with_broaden_retry(
            "flight", trip_request, notes=f"{_preference_notes(preferences, 'flight')} {_history_notes(history)}".strip()
        ),
        _search_with_broaden_retry(
            "accommodation",
            trip_request,
            notes=f"{_preference_notes(preferences, 'accommodation')} {_history_notes(history)}".strip(),
        ),
    )

    for category, results in (("flight", flight_results), ("accommodation", accommodation_results)):
        created = await add_research_options(tenant_id, session_id, category, results, attempt_number=1)
        for option in created:
            await events.publish(
                session_id, "card_ready", {"category": category, "option": option.__dict__}
            )


@traced("planner.research_category")
async def research_category(tenant_id: str, session_id: str, category: str, reason: str) -> dict:
    """spec FR-007: re-search only `category` from a stated rejection reason.
    spec FR-008: capped at 3 shown attempts — the 3rd rejection returns a
    manual-fallback payload (best options seen so far) instead of a 4th search.
    """
    current_attempt = await get_max_attempt_number(tenant_id, session_id, category)

    if current_attempt >= REJECT_CAP:
        all_options = await get_options(tenant_id, session_id, category)
        best = sorted(all_options, key=lambda o: o.attributes.get("price", float("inf")))[:5]
        payload = {"category": category, "best_options": [o.__dict__ for o in best]}
        await events.publish(session_id, "manual_fallback", payload)
        return {"status": "manual_fallback", "best_options": payload["best_options"]}

    next_attempt = current_attempt + 1
    await events.publish(session_id, "researching_again", {"category": category, "attempt_number": next_attempt})

    session = await get_session(tenant_id, session_id)
    results = await _search_with_broaden_retry(category, session.trip_request, notes=reason)

    created = await add_research_options(tenant_id, session_id, category, results, attempt_number=next_attempt)
    for option in created:
        await events.publish(session_id, "card_ready", {"category": category, "option": option.__dict__})

    return {"status": "researching"}


@traced("planner.handle_decision")
async def handle_decision(
    tenant_id: str, session_id: str, option_id: str, decision: str, shown_snapshot: dict
) -> None:
    await record_decision(tenant_id, option_id, decision, shown_snapshot)

    options = await get_options(tenant_id, session_id)
    by_category: dict[str, list] = {}
    for opt in options:
        by_category.setdefault(opt.category, []).append(opt)

    for category, opts in by_category.items():
        # Only the current attempt's batch decides completeness — options from
        # an earlier, already-rejected attempt don't count against a fresh one.
        current_attempt = max(o.attempt_number for o in opts)
        current_batch = [o for o in opts if o.attempt_number == current_attempt]
        selected = [o for o in current_batch if o.decision == "selected"]
        all_rejected = all(o.decision == "rejected" for o in current_batch)
        if selected:
            await events.publish(session_id, "category_complete", {"category": category, "outcome": "selected"})
        elif all_rejected:
            await events.publish(session_id, "category_complete", {"category": category, "outcome": "all_rejected"})

    all_complete = all(
        any(o.decision == "selected" for o in opts) for opts in by_category.values()
    ) and set(by_category.keys()) == set(CATEGORIES)

    if all_complete:
        await build_itinerary(tenant_id, session_id)


@traced("planner.build_itinerary")
async def build_itinerary(tenant_id: str, session_id: str) -> dict:
    """Assemble the itinerary once every category is resolved. Held on TripSession
    as the session's selected ResearchOptions plus computed total — not a
    separate persisted entity (data-model.md; noted during /speckit-analyze, F2).
    """
    session = await get_session(tenant_id, session_id)
    options = await get_options(tenant_id, session_id)
    selected = {o.category: o.attributes for o in options if o.decision == "selected"}

    total_cost = sum(
        float(attrs.get("price", 0)) for attrs in selected.values()
    )
    budget = (session.trip_request or {}).get("budget")

    itinerary = {"selections": selected, "total_cost": total_cost, "budget": budget}
    await set_itinerary(tenant_id, session_id, itinerary, total_cost)
    await update_session_status(tenant_id, session_id, "awaiting_approval")
    await events.publish(
        session_id, "itinerary_ready", {"itinerary": itinerary, "total_cost": total_cost, "budget": budget}
    )
    return itinerary
