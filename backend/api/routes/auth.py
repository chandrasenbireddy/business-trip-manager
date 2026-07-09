"""OAuth consent flow (spec FR-033, research.md §7): identity + calendar in
one consent step. No email-send scope — see research.md §7 for why
(confirmation emails go through the platform's own transactional service,
not the traveler's account).
"""

import os
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from agents.models.waitlist import activate, get_by_token, is_token_valid
from tools import secrets

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
SCOPES = "openid email profile https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/calendar.events"


@router.get("/login")
async def login(token: str, request: Request):
    """spec FR-032: re-checked here (before ever reaching Google) and again
    in /callback (before granting a session) — an expired or already-used
    token never gets this far being useful.
    """
    entry = await get_by_token(token)
    if entry is None or not is_token_valid(entry):
        raise HTTPException(400, "Invite link is invalid or has expired")

    client_id = secrets.resolve("btm/google_oauth_client_id")
    redirect_uri = f"{request.base_url}auth/callback"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": token,
        "access_type": "offline",  # calendar.events needs a refresh token, not just an access token
    }
    return RedirectResponse(f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}")


async def _exchange_code_for_identity(code: str) -> dict:
    """Real implementation exchanges `code` with Google's token endpoint and
    decodes the returned ID token. ponytail: stubbed pending a live OAuth
    client registration — the token-validation and identity-matching logic
    around this call is what's actually being tested (spec FR-032).
    """
    raise NotImplementedError("wire up the real Google token exchange here")


@router.get("/callback")
async def callback(code: str, state: str):
    token = state
    entry = await get_by_token(token)
    if entry is None or not is_token_valid(entry):
        raise HTTPException(400, "Invite link is invalid or has expired")

    identity = await _exchange_code_for_identity(code)
    if identity["email"] != entry.email:
        # spec FR-032: the invite MUST NOT grant access to any other identity.
        raise HTTPException(403, "This invite was issued to a different account")

    # Standalone-signup path: a new individual traveler becomes their own
    # single-person tenant (no org policy) — distinct from an enterprise
    # tenant, which PRD §8.1 has provisioned separately, outside this flow.
    tenant_id = entry.email
    await _ensure_tenant_and_user(tenant_id, entry.email, identity)
    await activate(entry.email)

    session_token = _issue_session(tenant_id, entry.email, is_admin=False)
    response = RedirectResponse("/trips")
    response.set_cookie("btm_session", session_token, httponly=True, secure=True, samesite="lax")
    return response


async def _ensure_tenant_and_user(tenant_id: str, email: str, identity: dict) -> None:
    from tools.db_context import tenant_connection, untenanted_connection

    # tenants has no RLS policy (it IS the scope), but users does — and this
    # tenant_id is brand new right here, so tenant_connection can set
    # app.tenant_id to it before either INSERT, same as any other write.
    async with untenanted_connection() as conn:
        await conn.execute(
            "INSERT INTO tenants (tenant_id, name) VALUES ($1, $1) ON CONFLICT (tenant_id) DO NOTHING",
            tenant_id,
        )
    async with tenant_connection(tenant_id) as conn:
        await conn.execute(
            "INSERT INTO users (user_id, tenant_id, google_sub) VALUES ($1, $2, $3) "
            "ON CONFLICT (user_id) DO UPDATE SET last_active_at = now()",
            email,
            tenant_id,
            identity.get("sub"),
        )
    # Real implementation writes identity["calendar_refresh_token"] to
    # Secret Manager at f"{email}/google_calendar_token" here.


def _issue_session(tenant_id: str, user_id: str, is_admin: bool) -> str:
    from authlib.jose import jwt

    return jwt.encode(
        {"alg": "HS256"},
        {"tenant_id": tenant_id, "user_id": user_id, "is_admin": is_admin},
        os.environ["BTM_SESSION_SECRET"],
    ).decode("utf-8")
