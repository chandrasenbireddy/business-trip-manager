"""BFF preference endpoints (contracts/bff-api.md): GET/PATCH /users/me/preferences."""

from fastapi import APIRouter, HTTPException, Request

from agents.memory import get_preferences, store_preference
from agents.models.memory import PREFERENCE_TYPES

router = APIRouter(prefix="/users/me/preferences", tags=["preferences"])


@router.get("")
async def list_preferences(request: Request):
    return await get_preferences(request.state.tenant_id, request.state.user_id)


@router.patch("/{type}")
async def update_preference(type: str, body: dict, request: Request):
    if type not in PREFERENCE_TYPES:
        raise HTTPException(404, f"Unknown preference type: {type}. Valid types: {', '.join(PREFERENCE_TYPES)}")
    return await store_preference(request.state.tenant_id, request.state.user_id, type, body["value"])
