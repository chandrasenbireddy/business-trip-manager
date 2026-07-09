"""Tenant-scoped DB access (constitution Principle VIII, research.md §6).

Every query MUST go through `tenant_connection`, which sets the `app.tenant_id`
session variable the Row-Level Security policies in 0002_rls.sql key off. The
helper itself has no isolation effect until those policies exist (T012) —
see tests/contract/test_tenant_isolation.py (T011), which is written to fail
until T012 lands.
"""

from contextlib import asynccontextmanager

import asyncpg

_pool: asyncpg.Pool | None = None


async def init_pool(dsn: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(dsn)


@asynccontextmanager
async def tenant_connection(tenant_id: str):
    """Yield a connection scoped to `tenant_id` for the duration of one transaction.

    Every query issued through this connection is subject to the RLS policies
    for that tenant_id — no query path exists that skips scoping.
    """
    if _pool is None:
        raise RuntimeError("db_context.init_pool() must be called before use")
    async with _pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.tenant_id', $1, true)", tenant_id)
            yield conn
