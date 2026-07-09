"""CostEvent (data-model.md) — spec FR-023.

Every agent/tool call that could incur cost records one of these; the
session cost-summary (tools/cost.py) aggregates them GROUP BY agent_type.
"""

import uuid
from dataclasses import dataclass

from tools.db_context import tenant_connection


@dataclass
class CostEvent:
    event_id: str
    session_id: str
    tenant_id: str
    user_id: str
    agent_type: str
    model_id: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


async def record_cost_event(
    tenant_id: str,
    session_id: str,
    user_id: str,
    agent_type: str,
    model_id: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
) -> CostEvent:
    event_id = str(uuid.uuid4())
    async with tenant_connection(tenant_id) as conn:
        await conn.execute(
            "INSERT INTO cost_events (event_id, session_id, tenant_id, user_id, agent_type, model_id, tokens_in, tokens_out, cost_usd) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
            event_id,
            session_id,
            tenant_id,
            user_id,
            agent_type,
            model_id,
            tokens_in,
            tokens_out,
            cost_usd,
        )
    return CostEvent(event_id, session_id, tenant_id, user_id, agent_type, model_id, tokens_in, tokens_out, cost_usd)


async def get_session_cost_summary(tenant_id: str, session_id: str) -> dict:
    """spec FR-023: session-end cost summary broken down by activity (agent_type)."""
    async with tenant_connection(tenant_id) as conn:
        rows = await conn.fetch(
            "SELECT agent_type, SUM(cost_usd) AS total FROM cost_events "
            "WHERE tenant_id = $1 AND session_id = $2 GROUP BY agent_type",
            tenant_id,
            session_id,
        )
        total_row = await conn.fetchrow(
            "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM cost_events WHERE tenant_id = $1 AND session_id = $2",
            tenant_id,
            session_id,
        )
    return {
        "by_activity": {r["agent_type"]: float(r["total"]) for r in rows},
        "total": float(total_row["total"]),
    }


async def get_tenant_cost_usage(tenant_id: str) -> dict:
    """spec FR-022 (US4's admin dashboard) — tenant-wide, by user and by
    agent_type. Moved here from agents/models/session.py once this dedicated
    module existed (T089); the query itself is unchanged.
    """
    async with tenant_connection(tenant_id) as conn:
        by_user = await conn.fetch(
            "SELECT user_id, SUM(cost_usd) AS total FROM cost_events WHERE tenant_id = $1 GROUP BY user_id",
            tenant_id,
        )
        by_agent_type = await conn.fetch(
            "SELECT agent_type, SUM(cost_usd) AS total FROM cost_events WHERE tenant_id = $1 GROUP BY agent_type",
            tenant_id,
        )
        total_row = await conn.fetchrow(
            "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM cost_events WHERE tenant_id = $1", tenant_id
        )
    return {
        "by_user": {r["user_id"]: float(r["total"]) for r in by_user},
        "by_agent_type": {r["agent_type"]: float(r["total"]) for r in by_agent_type},
        "total": float(total_row["total"]),
    }
