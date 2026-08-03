"""BTM FastAPI BFF — auth, session routing, SSE relay, waitlist management (PRD §8.1)."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from api.middleware.auth import SessionAuthMiddleware
from api.routes import admin, airbnb, auth, preferences, trips, waitlist
from tools import db_context


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The asyncpg pool MUST be created in the loop that will actually serve
    # requests — creating it elsewhere (e.g. an external script's own loop)
    # produces "another operation is in progress" errors on first use.
    await db_context.init_pool(os.environ["BTM_DATABASE_URL"])
    yield


app = FastAPI(title="Business Travel Manager BFF", lifespan=lifespan)

app.add_middleware(SessionAuthMiddleware, session_secret=os.environ["BTM_SESSION_SECRET"])
app.include_router(trips.router)
app.include_router(preferences.router)
app.include_router(admin.router)
app.include_router(airbnb.router)
app.include_router(waitlist.router)
app.include_router(waitlist.admin_router)
app.include_router(auth.router)


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
