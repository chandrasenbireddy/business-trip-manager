"""TripSession, ResearchOption, ApprovalEvent data access (data-model.md).

Every function takes tenant_id explicitly and goes through
tools.db_context.tenant_connection — there is no query path that bypasses
RLS scoping.
"""

import uuid
from dataclasses import dataclass

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
    attempt_number: int = 1


async def create_session(tenant_id: str, user_id: str, trip_request: dict) -> TripSession:
    session_id = str(uuid.uuid4())
    async with tenant_connection(tenant_id) as conn:
        await conn.execute(
            "INSERT INTO sessions (session_id, user_id, tenant_id, status, trip_request) VALUES ($1, $2, $3, 'in_progress', $4)",
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


async def list_sessions_for_user(tenant_id: str, user_id: str, limit: int = 20) -> list[dict]:
    """History page (spec Story 3, T065) — most recent first."""
    async with tenant_connection(tenant_id) as conn:
        rows = await conn.fetch(
            "SELECT session_id, trip_request, status, created_at FROM sessions WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            user_id,
            limit,
        )
    return [
        {
            "session_id": r["session_id"],
            "destination": (r["trip_request"] or {}).get("destination"),
            "status": r["status"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


async def update_session_status(tenant_id: str, session_id: str, status: str) -> None:
    async with tenant_connection(tenant_id) as conn:
        await conn.execute("UPDATE sessions SET status = $1 WHERE session_id = $2", status, session_id)


async def update_trip_request(tenant_id: str, session_id: str, trip_request: dict) -> None:
    """Fix: trip intake flow — a session created while origin is still
    unknown (awaiting_clarification) needs its stored trip_request updated
    once the traveler answers, so build_itinerary/history reads see it.
    """
    async with tenant_connection(tenant_id) as conn:
        await conn.execute("UPDATE sessions SET trip_request = $1 WHERE session_id = $2", trip_request, session_id)


async def set_itinerary(tenant_id: str, session_id: str, itinerary: dict, total_cost_usd: float) -> None:
    async with tenant_connection(tenant_id) as conn:
        await conn.execute(
            "UPDATE sessions SET itinerary = $1, total_cost_usd = $2 WHERE session_id = $3",
            itinerary,
            total_cost_usd,
            session_id,
        )


async def add_research_options(
    tenant_id: str, session_id: str, category: str, options: list[dict], attempt_number: int = 1
) -> list[ResearchOption]:
    """A `badge` key on an option dict (spec FR-028: "wishlisted" | "past_stay")
    is stored in its own column, not folded into `attributes` — pop it here
    rather than making every caller remember to strip it before persisting.
    """
    created = []
    async with tenant_connection(tenant_id) as conn:
        for option in options:
            attrs = dict(option)
            badge = attrs.pop("badge", None)
            option_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO research_options (option_id, session_id, tenant_id, category, attributes, attempt_number, badge) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                option_id,
                session_id,
                tenant_id,
                category,
                attrs,
                attempt_number,
                badge,
            )
            created.append(
                ResearchOption(
                    option_id,
                    session_id,
                    tenant_id,
                    category,
                    attrs,
                    badge=badge,
                    attempt_number=attempt_number,
                )
            )
    return created


async def get_max_attempt_number(tenant_id: str, session_id: str, category: str) -> int:
    async with tenant_connection(tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT COALESCE(MAX(attempt_number), 0) AS max_attempt FROM research_options WHERE session_id = $1 AND category = $2",
            session_id,
            category,
        )
    return row["max_attempt"]


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
            attempt_number=r["attempt_number"],
        )
        for r in rows
    ]


async def record_decision(tenant_id: str, option_id: str, decision: str, shown_snapshot: dict) -> None:
    """Records the swipe decision AND its immutable audit event in one transaction
    (constitution Principle X — every decision is auditable, not just the current state).
    """
    async with tenant_connection(tenant_id) as conn:
        row = await conn.fetchrow(
            "UPDATE research_options SET decision = $1, decided_at = now() WHERE option_id = $2 RETURNING session_id",
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


async def get_approval_events(tenant_id: str, limit: int = 100) -> list[dict]:
    """Audit trail (spec FR-020) — read-only; there is deliberately no
    corresponding update/delete function anywhere in this module.
    """
    async with tenant_connection(tenant_id) as conn:
        rows = await conn.fetch(
            "SELECT event_id, session_id, option_id, decision, shown_snapshot, created_at "
            "FROM approval_events WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2",
            tenant_id,
            limit,
        )
    return [dict(r) for r in rows]
