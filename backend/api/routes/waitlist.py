"""BFF waitlist endpoints (contracts/bff-api.md): submit + admin approval (Story 7)."""

from fastapi import APIRouter, Depends, HTTPException

from agents.models.waitlist import approve_and_invite, submit_request
from api.middleware.admin import require_admin
from tools import secrets

router = APIRouter(prefix="/waitlist", tags=["waitlist"])

# Waitlist approval is a platform-level admin action (spec FR-032 says "an
# administrator", not "the tenant's administrator" like FR-020/022 do — there
# is no tenant yet at this point) — any authenticated admin can approve,
# regardless of which tenant they administer.
admin_router = APIRouter(prefix="/admin/waitlist", tags=["waitlist"], dependencies=[Depends(require_admin)])


@router.post("")
async def submit_waitlist_request(body: dict):
    entry = await submit_request(body["email"])
    return {"status": entry.status}


@admin_router.post("/{email}/approve")
async def approve_waitlist_request(email: str):
    try:
        entry = await approve_and_invite(email)
    except ValueError:
        raise HTTPException(404, f"No waitlist entry for {email!r}")
    await _send_invite_email(email, entry.activation_token)
    return {"status": entry.status}


async def _send_invite_email(email: str, token: str) -> None:
    """Sent via the platform's transactional email credential, same pattern as
    agents.booking.send_email — stubbed pending a live provider.
    """
    secrets.resolve("btm/transactional_email_api_key")
    # Real implementation uses the resolved key to email a link like
    # /auth/login?token={token} to `email`.
