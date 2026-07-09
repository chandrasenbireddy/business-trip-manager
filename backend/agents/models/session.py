"""TripSession, ResearchOption, ApprovalEvent data access (data-model.md).

Every function takes tenant_id explicitly and goes through
tools.db_context.tenant_connection — there is no query path that bypasses
RLS scoping.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from tools.db_context import tenant_connection


@dataclass
class TripSession:
    session_id: str
    user_id: str
    tenant_id: str
    status: str
    trip_request: dict
    itinerary: dict | None = None
    total_cost_usd: float = 0.0


@dataclass
class ResearchOption:
    option_id: str
    session_id: str
    tenant_id: str
    category: str
    attributes: dict
    decision: str = "pending"
    badge: str | None = None


async def create_session(tenant_id: str, user_id: str, trip_request: dict) -> TripSession:
    session_id = str(uuid.uuid4())
    async with tenant_connection(tenant_id) as conn:
        await conn.execute(
            "INSERT INTO sessions (session_id, user_id, tenant_id, status, trip_request) "
            "VALUES ($1, $2, $3, 'in_progress', $4)",
            session_id,
            user_id,
            tenant_id,
            trip_request,
        )
    return TripSession(session_id, user_id, tenant_id, "in_progress", trip_request)


async def get_session(tenant_id: str, session_id: str) -> TripSession | None:
    async with tenant_connection(tenant_id) as conn:
        row = await conn.fetchrow("SELECT * FROM sessions WHERE session_id = $1", session_id)
    if row is None:
        return None
    return TripSession(
        session_id=row["session_id"],
        user_id=row["user_id"],
        tenant_id=row["tenant_id"],
        status=row["status"],
        trip_request=row["trip_request"],
        itinerary=row["itinerary"],
        total_cost_usd=float(row["total_cost_usd"]),
    )


async def update_session_status(tenant_id: str, session_id: str, status: str) -> None:
    async with tenant_connection(tenant_id) as conn:
        await conn.execute(
            "UPDATE sessions SET status = $1 WHERE session_id = $2", status, session_id
        )


async def set_itinerary(tenant_id: str, session_id: str, itinerary: dict, total_cost_usd: float) -> None:
    async with tenant_connection(tenant_id) as conn:
        await conn.execute(
            "UPDATE sessions SET itinerary = $1, total_cost_usd = $2 WHERE session_id = $3",
            itinerary,
            total_cost_usd,
            session_id,
        )


async def add_research_options(tenant_id: str, session_id: str, category: str, options: list[dict]) -> list[ResearchOption]:
    created = []
    async with tenant_connection(tenant_id) as conn:
        for attrs in options:
            option_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO research_options (option_id, session_id, tenant_id, category, attributes) "
                "VALUES ($1, $2, $3, $4, $5)",
                option_id,
                session_id,
                tenant_id,
                category,
                attrs,
            )
            created.append(ResearchOption(option_id, session_id, tenant_id, category, attrs))
    return created


async def get_options(tenant_id: str, session_id: str, category: str | None = None) -> list[ResearchOption]:
    query = "SELECT * FROM research_options WHERE session_id = $1"
    params = [session_id]
    if category:
        query += " AND category = $2"
        params.append(category)
    async with tenant_connection(tenant_id) as conn:
        rows = await conn.fetch(query, *params)
    return [
        ResearchOption(
            option_id=r["option_id"],
            session_id=r["session_id"],
            tenant_id=r["tenant_id"],
            category=r["category"],
            attributes=r["attributes"],
            decision=r["decision"],
            badge=r["badge"],
        )
        for r in rows
    ]


async def record_decision(tenant_id: str, option_id: str, decision: str, shown_snapshot: dict) -> None:
    """Records the swipe decision AND its immutable audit event in one transaction
    (constitution Principle X — every decision is auditable, not just the current state).
    """
    async with tenant_connection(tenant_id) as conn:
        row = await conn.fetchrow(
            "UPDATE research_options SET decision = $1, decided_at = now() "
            "WHERE option_id = $2 RETURNING session_id",
            decision,
            option_id,
        )
        await conn.execute(
            "INSERT INTO approval_events (event_id, session_id, tenant_id, option_id, decision, shown_snapshot) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            str(uuid.uuid4()),
            row["session_id"],
            tenant_id,
            option_id,
            decision,
            shown_snapshot,
        )


async def record_confirmation(tenant_id: str, session_id: str, shown_snapshot: dict) -> None:
    async with tenant_connection(tenant_id) as conn:
        await conn.execute(
            "INSERT INTO approval_events (event_id, session_id, tenant_id, option_id, decision, shown_snapshot) "
            "VALUES ($1, $2, $3, NULL, 'itinerary_confirmed', $4)",
            str(uuid.uuid4()),
            session_id,
            tenant_id,
            shown_snapshot,
        )
