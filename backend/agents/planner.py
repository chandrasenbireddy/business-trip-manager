"""Planner agent: parallel research dispatch, results merge, itinerary assembly.

spec FR-003 (parallel dispatch), FR-005/FR-006 (card_ready/category_complete),
FR-009 (build_itinerary).
"""

import asyncio

from agents.base import traced
from agents.models.session import (
    add_research_options,
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


@traced("planner.run_research")
async def run_research(session_id: str, tenant_id: str, trip_request: dict) -> None:
    await events.publish(session_id, "research_started", {"categories": list(CATEGORIES)})

    flight_task = search_flights(
        origin=trip_request.get("origin", ""),
        destination=trip_request["destination"],
        depart_date=trip_request["start_date"],
        return_date=trip_request.get("end_date"),
    )
    reference_point = trip_request.get("reference_point", {"lat": 0.0, "lng": 0.0})
    airbnb_task = search_airbnb(
        destination=trip_request["destination"],
        reference_point=reference_point,
        checkin=trip_request["start_date"],
        checkout=trip_request["end_date"],
    )

    flight_results, accommodation_results = await asyncio.gather(flight_task, airbnb_task)

    for category, results in (("flight", flight_results), ("accommodation", accommodation_results)):
        created = await add_research_options(tenant_id, session_id, category, results)
        for option in created:
            await events.publish(
                session_id, "card_ready", {"category": category, "option": option.__dict__}
            )


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
        selected = [o for o in opts if o.decision == "selected"]
        all_rejected = all(o.decision == "rejected" for o in opts)
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
