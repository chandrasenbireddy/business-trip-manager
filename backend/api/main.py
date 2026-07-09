"""BTM FastAPI BFF — auth, session routing, SSE relay, waitlist management (PRD §8.1)."""

import os

from fastapi import FastAPI, Request

from api.middleware.auth import SessionAuthMiddleware

app = FastAPI(title="Business Travel Manager BFF")

app.add_middleware(SessionAuthMiddleware, session_secret=os.environ["BTM_SESSION_SECRET"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/users/me")
async def me(request: Request):
    return {
        "user_id": request.state.user_id,
        "tenant_id": request.state.tenant_id,
        "is_admin": request.state.is_admin,
    }


# Routers are added per user story as they're implemented:
#   from api.routes import trips, preferences, admin, waitlist, airbnb, auth
#   app.include_router(trips.router)
#   ...
