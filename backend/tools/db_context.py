"""Tenant-scoped DB access (constitution Principle VIII, research.md §6).

Every query MUST go through `tenant_connection`, which sets the `app.tenant_id`
session variable the Row-Level Security policies in 0002_rls.sql key off. The
helper itself has no isolation effect until those policies exist (T012) —
see tests/contract/test_tenant_isolation.py (T011), which is written to fail
until T012 lands.
"""

import json
import os
from contextlib import asynccontextmanager

import asyncpg

_pool: asyncpg.Pool | None = None


async def _register_jsonb_codec(conn: asyncpg.Connection) -> None:
    # asyncpg has no built-in dict<->jsonb marshalling — every connection in
    # the pool needs this or `dict` params to jsonb columns raise DataError.
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def init_pool(dsn: str) -> None:
    global _pool
    # BTM_DB_POOL_MIN/MAX default small (1/3) so the test suite — which
    # re-inits this pool per test without ever closing the prior one — never
    # exhausts Postgres's connection limit. A real deployment under
    # concurrent tenant load (T107) must override these via env, or every
    # request beyond the 3rd queues behind the same 3 connections regardless
    # of traffic.
    min_size = int(os.environ.get("BTM_DB_POOL_MIN", "1"))
    max_size = int(os.environ.get("BTM_DB_POOL_MAX", "3"))
    _pool = await asyncpg.create_pool(dsn, init=_register_jsonb_codec, min_size=min_size, max_size=max_size)


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


@asynccontextmanager
async def untenanted_connection():
    """For the handful of tables that genuinely have no tenant yet — waitlist
    rows exist before a tenant is ever created (spec FR-031/FR-032). Callers
    MUST NOT use this for any tenant-scoped table.

    A plain `from tools.db_context import _pool` at another module's import
    time would capture `None` and never see a later `init_pool()` reassign
    it — this accesses the module-level name fresh on every call instead.
    """
    if _pool is None:
        raise RuntimeError("db_context.init_pool() must be called before use")
    async with _pool.acquire() as conn:
        yield conn
