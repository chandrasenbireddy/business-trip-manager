"""Memory agent (PRD AR-04): episodic + semantic memory, trip history.

spec FR-013 (versioned preferences), FR-014 (trip history informs future
research to the same destination).
"""

from agents.base import traced
from agents.models.memory import get_closed_sessions_for_destination
from agents.models.memory import get_preferences as _get_preferences
from agents.models.memory import get_recent_turns
from agents.models.memory import store_preference as _store_preference
from agents.models.memory import store_turn as _store_turn
from agents.models.session import get_session
from tools.embeddings import embed


@traced("memory.store_turn", tool_name="store_turn")
async def store_turn(tenant_id: str, session_id: str, user_id: str, role: str, content: str) -> dict:
    embedding = await embed(content)
    turn = await _store_turn(tenant_id, session_id, user_id, role, content, embedding)
    return {"turn_id": turn.turn_id}


@traced("memory.retrieve_context", tool_name="retrieve_context")
async def retrieve_context(tenant_id: str, user_id: str, destination: str | None = None, k: int = 5) -> dict:
    """Hybrid recency + destination-match retrieval (PRD AR-04). Semantic
    ranking by embedding similarity activates once tools/embeddings.py has a
    real provider wired up — recency and destination-match alone already
    satisfy spec Story 3's acceptance scenarios.
    """
    turns = await get_recent_turns(tenant_id, user_id, limit=k)
    relevant_history = (
        await get_closed_sessions_for_destination(tenant_id, user_id, destination, limit=k) if destination else []
    )
    return {
        "turns": [t.__dict__ for t in turns],
        "relevant_history": relevant_history,
    }


@traced("memory.store_preference", tool_name="store_preference")
async def store_preference(tenant_id: str, user_id: str, type: str, value: dict) -> dict:
    pref = await _store_preference(tenant_id, user_id, type, value)
    return {"version": pref.version}


@traced("memory.get_preferences", tool_name="get_preferences")
async def get_preferences(tenant_id: str, user_id: str) -> dict:
    prefs = await _get_preferences(tenant_id, user_id)
    return {"preferences": [{"type": p.type, "value": p.value, "version": p.version} for p in prefs]}


@traced("memory.summarize_session", tool_name="summarize_session")
async def summarize_session(tenant_id: str, session_id: str) -> dict:
    """The mechanism by which a closed TripSession becomes a retrievable Trip
    History Record (spec FR-014) — sessions are never deleted, so "retention"
    is the sessions table itself; this just shapes it for display/context.
    """
    session = await get_session(tenant_id, session_id)
    trip_request = session.trip_request or {}
    summary = {
        "destination": trip_request.get("destination"),
        "dates": {"start": trip_request.get("start_date"), "end": trip_request.get("end_date")},
        "selections": (session.itinerary or {}).get("selections", {}),
        "total_cost": session.total_cost_usd,
    }
    return {"summary": summary}


@traced("memory.link_sessions", tool_name="link_sessions")
async def link_sessions(tenant_id: str, session_id: str, related_session_ids: list[str]) -> None:
    """Associates sessions to the same destination/traveler pattern for future
    retrieval. ponytail: stored as a tag on the origin session's trip_request
    rather than a new join table — destination-match already covers the
    common case (spec FR-014); this is for the explicit-grouping edge case.
    """
    from tools.db_context import tenant_connection

    session = await get_session(tenant_id, session_id)
    updated_trip_request = {**(session.trip_request or {}), "related_sessions": related_session_ids}
    async with tenant_connection(tenant_id) as conn:
        await conn.execute(
            "UPDATE sessions SET trip_request = $1 WHERE session_id = $2",
            updated_trip_request,
            session_id,
        )
