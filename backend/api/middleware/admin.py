"""Admin-role check (spec FR-020/FR-022; contracts/bff-api.md cross-cutting rules).

A non-admin caller gets 403, never a filtered/empty response — the caller
should know they were denied, not think the tenant simply has no data.
"""

from fastapi import HTTPException, Request


def require_admin(request: Request) -> None:
    if not request.state.is_admin:
        raise HTTPException(403, "Admin role required")
