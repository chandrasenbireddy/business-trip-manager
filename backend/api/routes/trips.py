"""BFF trip endpoints (contracts/bff-api.md): POST /trips, GET /trips/{id},
GET /trips/{id}/stream, decision, confirm.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from agents import booking, planner
from agents.models.session import get_options, get_session, record_confirmation
from agents.orchestrator import handle_trip_request
from tools import events

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post("")
async def create_trip(request: Request, body: dict):
    result = await handle_trip_request(
        description=body["description"],
        user_id=request.state.user_id,
        tenant_id=request.state.tenant_id,
    )
    if "clarifying_question" in result:
        return {"session_id": None, "status": "clarifying_question", **result}
    return result


@router.get("/{session_id}")
async def get_trip(session_id: str, request: Request):
    session = await get_session(request.state.tenant_id, session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    options = await get_options(request.state.tenant_id, session_id)
    by_category: dict[str, list] = {}
    for opt in options:
        by_category.setdefault(opt.category, []).append(opt)

    categories = []
    for name, opts in by_category.items():
        current_attempt = max(o.attempt_number for o in opts)
        current_batch = [o for o in opts if o.attempt_number == current_attempt]
        if any(o.decision == "selected" for o in current_batch):
            status = "selected"
        elif all(o.decision == "rejected" for o in current_batch):
            status = "all_rejected"
        else:
            status = "selecting"
        categories.append({"name": name, "status": status, "options": [o.__dict__ for o in current_batch]})

    return {
        "status": session.status,
        "categories": categories,
        "itinerary": session.itinerary,
    }


@router.get("/{session_id}/stream")
async def stream_trip(session_id: str):
    async def event_stream():
        async for event, data in events.subscribe(session_id):
            yield events.format_sse(event, data)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{session_id}/options/{option_id}/decision")
async def record_option_decision(session_id: str, option_id: str, body: dict, request: Request):
    tenant_id = request.state.tenant_id
    options = await get_options(tenant_id, session_id)
    option = next((o for o in options if o.option_id == option_id), None)
    if option is None:
        raise HTTPException(404, "Option not found")

    await planner.handle_decision(
        tenant_id, session_id, option_id, body["decision"], shown_snapshot=option.attributes
    )
    return {"category_status": "recorded"}


@router.post("/{session_id}/categories/{category}/research")
async def research_category(session_id: str, category: str, body: dict, request: Request):
    """spec FR-007/FR-008: re-search one category from a stated rejection reason,
    capped at 3 shown attempts (contracts/bff-api.md)."""
    result = await planner.research_category(
        request.state.tenant_id, session_id, category, reason=body.get("reason", "")
    )
    return result


@router.post("/{session_id}/confirm")
async def confirm_trip(session_id: str, request: Request):
    tenant_id = request.state.tenant_id
    session = await get_session(tenant_id, session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    if session.status != "awaiting_approval":
        # spec FR-010: booking is unreachable before this state, enforced at the
        # BFF as well as inside execute_booking itself (constitution Principle IX).
        raise HTTPException(409, "Itinerary is not ready for confirmation")

    await record_confirmation(tenant_id, session_id, shown_snapshot=session.itinerary)
    from agents.models.session import update_session_status

    await update_session_status(tenant_id, session_id, "confirmed")

    result = await booking.execute_booking(
        session_id=session_id, session_status="confirmed", itinerary=session.itinerary
    )
    return {"status": result["status"]}
