"""BFF admin endpoints (contracts/bff-api.md): policy, approval-events audit, cost usage.

Every route here depends on require_admin — a non-admin caller gets 403
(spec FR-020/FR-022 cross-cutting rule), never a filtered/empty response.
"""

from fastapi import APIRouter, Depends, Request

from agents.models.session import get_approval_events, get_cost_usage
from agents.models.tenant import get_tenant, set_policy
from api.middleware.admin import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/policy")
async def read_policy(request: Request):
    tenant = await get_tenant(request.state.tenant_id)
    policy = tenant.travel_policy if tenant else None
    return {"policy": policy.__dict__ if policy else {}}


@router.put("/policy")
async def update_policy(body: dict, request: Request):
    policy = await set_policy(request.state.tenant_id, body)
    return {"policy": policy.__dict__}


@router.get("/approval-events")
async def list_approval_events(request: Request):
    events = await get_approval_events(request.state.tenant_id)
    return {"events": events}


@router.get("/cost-usage")
async def cost_usage(request: Request):
    return await get_cost_usage(request.state.tenant_id)
