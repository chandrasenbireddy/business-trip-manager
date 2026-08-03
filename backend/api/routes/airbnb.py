"""BFF Airbnb account endpoints (contracts/bff-api.md): status, reconnect (Story 5)."""

from fastapi import APIRouter, Request

from agents.memory import get_airbnb_context

router = APIRouter(prefix="/users/me", tags=["airbnb"])


@router.get("/airbnb-status")
async def airbnb_status(request: Request):
    context = await get_airbnb_context(request.state.user_id)
    return {"connected": context["connected"], "cookie_status": context["cookie_status"]}


@router.post("/airbnb-reconnect")
async def airbnb_reconnect(request: Request):
    # Real implementation kicks off a fresh Airbnb OAuth/session-capture flow
    # and writes the new session cookie to Secret Manager — stubbed the same
    # way as the other not-yet-live external connections (spec FR-029).
    return {"status": "reconnecting"}
