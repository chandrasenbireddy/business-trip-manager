"""Session-derived tenant_id/user_id resolution (spec FR-034).

MUST NOT accept tenant_id/user_id as client-supplied fields (query params, body,
headers) — the only source of truth is the signed session cookie issued after
OAuth consent (api/routes/auth.py).
"""

from authlib.jose import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_UNAUTHENTICATED_PATHS = {"/waitlist", "/auth/callback", "/health"}


class SessionAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, session_secret: str):
        super().__init__(app)
        self._secret = session_secret

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _UNAUTHENTICATED_PATHS:
            return await call_next(request)

        token = request.cookies.get("btm_session")
        if not token:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        try:
            claims = jwt.decode(token, self._secret)
            claims.validate()
        except Exception:
            return JSONResponse({"detail": "Invalid or expired session"}, status_code=401)

        # The only place tenant_id/user_id enter request state — never from
        # client-supplied path/query/body values (spec FR-034).
        request.state.tenant_id = claims["tenant_id"]
        request.state.user_id = claims["user_id"]
        request.state.is_admin = claims.get("is_admin", False)
        return await call_next(request)
