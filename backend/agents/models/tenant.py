"""Tenant + embedded Organization Travel Policy (data-model.md).

All policy fields are optional at the tenant level — an unset policy means
no filtering/approval-gating occurs for that tenant (spec Assumptions).
"""

from dataclasses import dataclass, field

from tools.db_context import tenant_connection


@dataclass
class OrganizationTravelPolicy:
    max_flight_budget: float | None = None
    max_hotel_budget_per_night: float | None = None
    approved_airlines: list[str] = field(default_factory=list)
    approval_threshold: float | None = None
    # Not in data-model.md's original field list — added here because FR-019
    # requires notifying "a designated approver," and nothing else identifies
    # one. Lives inside the existing travel_policy JSONB, no new column needed.
    approver_email: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "OrganizationTravelPolicy":
        return cls(
            max_flight_budget=data.get("max_flight_budget"),
            max_hotel_budget_per_night=data.get("max_hotel_budget_per_night"),
            approved_airlines=data.get("approved_airlines", []),
            approval_threshold=data.get("approval_threshold"),
            approver_email=data.get("approver_email"),
        )


@dataclass
class Tenant:
    tenant_id: str
    name: str
    travel_policy: OrganizationTravelPolicy
    seat_quota: int | None = None


async def get_tenant(tenant_id: str) -> Tenant | None:
    async with tenant_connection(tenant_id) as conn:
        row = await conn.fetchrow("SELECT * FROM tenants WHERE tenant_id = $1", tenant_id)
    if row is None:
        return None
    return Tenant(
        tenant_id=row["tenant_id"],
        name=row["name"],
        travel_policy=OrganizationTravelPolicy.from_dict(row["travel_policy"] or {}),
        seat_quota=row["seat_quota"],
    )


async def set_policy(tenant_id: str, updates: dict) -> OrganizationTravelPolicy:
    """Merges `updates` into the existing policy — an admin setting one field
    (e.g. approval_threshold) doesn't clobber the others.
    """
    async with tenant_connection(tenant_id) as conn:
        row = await conn.fetchrow(
            "UPDATE tenants SET travel_policy = travel_policy || $1 "
            "WHERE tenant_id = $2 RETURNING travel_policy",
            updates,
            tenant_id,
        )
    return OrganizationTravelPolicy.from_dict(row["travel_policy"])
