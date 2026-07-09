"""Session-derived tenant_id/user_id resolution (spec FR-034).

MUST NOT accept tenant_id/user_id as client-supplied fields (query params, body,
headers) — the only source of truth is the signed session cookie issued after
OAuth consent (api/routes/auth.py).

Implemented as pure ASGI middleware, NOT `starlette.middleware.base.BaseHTTPMiddleware`
— BaseHTTPMiddleware relays the downstream response through an internal
anyio memory-stream task, which cannot forward a genuinely long-lived
StreamingResponse (our SSE endpoint) correctly; requests through it hang
waiting on the first chunk. Plain ASGI middleware has no such relay.
"""

import uuid

from authlib.jose import jwt
from fastapi import Request
from fastapi.responses import JSONResponse

from tools.telemetry import RunContext, run_context

_UNAUTHENTICATED_PATHS = {"/waitlist", "/auth/login", "/auth/callback", "/health"}


def _session_id_from_path(path: str) -> str:
    # ponytail: cheap manual parse instead of relying on Starlette's routed
    # path_params, which aren't resolved yet at this layer — every
    # session-scoped route is /trips/{session_id}[...], so this is enough.
    parts = path.strip("/").split("/")
    return parts[1] if len(parts) > 1 and parts[0] == "trips" else "pending"


class SessionAuthMiddleware:
    def __init__(self, app, session_secret: str):
        self.app = app
        self._secret = session_secret

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive=receive)

        if request.url.path in _UNAUTHENTICATED_PATHS:
            return await self.app(scope, receive, send)

        token = request.cookies.get("btm_session")
        if not token:
            response = JSONResponse({"detail": "Not authenticated"}, status_code=401)
            return await response(scope, receive, send)

        try:
            claims = jwt.decode(token, self._secret)
            claims.validate()
        except Exception:
            response = JSONResponse({"detail": "Invalid or expired session"}, status_code=401)
            return await response(scope, receive, send)

        # The only place tenant_id/user_id enter request state — never from
        # client-supplied path/query/body values (spec FR-034).
        scope.setdefault("state", {})
        scope["state"]["tenant_id"] = claims["tenant_id"]
        scope["state"]["user_id"] = claims["user_id"]
        scope["state"]["is_admin"] = claims.get("is_admin", False)

        # Ambient telemetry context for every @traced call this request makes
        # (constitution Principle XV) — tenant.id/session.id must never be
        # missing from a span, so this is established here, once, per request.
        ctx = RunContext(
            tenant_id=claims["tenant_id"],
            session_id=_session_id_from_path(request.url.path),
            agent_id="btm-api",
            agent_version="0.1.0",
            graph_run_id=str(uuid.uuid4()),
        )
        with run_context(ctx):
            await self.app(scope, receive, send)
