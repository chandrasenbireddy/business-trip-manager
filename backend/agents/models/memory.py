"""TravelerPreference, ConversationTurn (Trip History Record) data access (data-model.md).

Preferences are versioned and never overwritten in place (spec FR-013) —
editing one inserts a new row and sets `superseded_by` on the prior version.
"""

import uuid
from dataclasses import dataclass

from tools.db_context import tenant_connection

PREFERENCE_TYPES = ("seat", "hotel_proximity", "dietary", "preferred_airline", "budget_pattern", "home_city")


@dataclass
class TravelerPreference:
    preference_id: str
    user_id: str
    tenant_id: str
    type: str
    value: dict
    version: int
    superseded_by: str | None = None


@dataclass
class ConversationTurn:
    turn_id: str
    session_id: str
    tenant_id: str
    user_id: str
    role: str
    content: str


async def store_turn(
    tenant_id: str,
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    embedding: list[float] | None = None,
) -> ConversationTurn:
    turn_id = str(uuid.uuid4())
    async with tenant_connection(tenant_id) as conn:
        await conn.execute(
            "INSERT INTO conversation_turns (turn_id, session_id, tenant_id, user_id, role, content, embedding) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)",
            turn_id,
            session_id,
            tenant_id,
            user_id,
            role,
            content,
            embedding,
        )
    return ConversationTurn(turn_id, session_id, tenant_id, user_id, role, content)


async def get_recent_turns(tenant_id: str, user_id: str, limit: int = 5) -> list[ConversationTurn]:
    async with tenant_connection(tenant_id) as conn:
        rows = await conn.fetch(
            "SELECT * FROM conversation_turns WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
            user_id,
            limit,
        )
    return [ConversationTurn(r["turn_id"], r["session_id"], r["tenant_id"], r["user_id"], r["role"], r["content"]) for r in rows]


async def get_closed_sessions_for_destination(tenant_id: str, user_id: str, destination: str, limit: int = 5) -> list[dict]:
    async with tenant_connection(tenant_id) as conn:
        rows = await conn.fetch(
            "SELECT session_id, trip_request, itinerary, created_at FROM sessions "
            "WHERE user_id = $1 AND status IN ('confirmed', 'closed') "
            "AND trip_request->>'destination' = $2 "
            "ORDER BY created_at DESC LIMIT $3",
            user_id,
            destination,
            limit,
        )
    return [dict(r) for r in rows]


async def store_preference(tenant_id: str, user_id: str, type: str, value: dict) -> TravelerPreference:
    """Always creates a new version — never overwrites in place (spec FR-013)."""
    async with tenant_connection(tenant_id) as conn:
        prior = await conn.fetchrow(
            "SELECT preference_id, version FROM semantic_memories "
            "WHERE user_id = $1 AND type = $2 AND superseded_by IS NULL "
            "ORDER BY version DESC LIMIT 1",
            user_id,
            type,
        )
        next_version = (prior["version"] + 1) if prior else 1
        new_id = str(uuid.uuid4())
        await conn.execute(
            "INSERT INTO semantic_memories (preference_id, tenant_id, user_id, type, value, version) VALUES ($1, $2, $3, $4, $5, $6)",
            new_id,
            tenant_id,
            user_id,
            type,
            value,
            next_version,
        )
        if prior:
            await conn.execute(
                "UPDATE semantic_memories SET superseded_by = $1 WHERE preference_id = $2",
                new_id,
                prior["preference_id"],
            )
    return TravelerPreference(new_id, user_id, tenant_id, type, value, next_version)


async def get_preferences(tenant_id: str, user_id: str) -> list[TravelerPreference]:
    """Current version per type only — superseded versions are retained but not returned here."""
    async with tenant_connection(tenant_id) as conn:
        rows = await conn.fetch(
            "SELECT * FROM semantic_memories WHERE user_id = $1 AND superseded_by IS NULL",
            user_id,
        )
    return [
        TravelerPreference(
            r["preference_id"],
            r["user_id"],
            r["tenant_id"],
            r["type"],
            r["value"],
            r["version"],
            r["superseded_by"],
        )
        for r in rows
    ]
