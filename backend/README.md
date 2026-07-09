# BTM Backend

Multi-agent backend for Business Travel Manager: orchestrator, planner, booking, and memory agents (AWS Strands SDK), flights/Airbnb scrapers (browser-use), and the FastAPI BFF.

See `specs/001-business-travel-manager/` in the [btm Speckit workspace](https://github.com/chandrasenbireddy) for the full spec, plan, data model, and API/tool contracts this implementation follows.

## Layout

- `agents/` — orchestrator, planner, booking, memory (Strands agents)
- `scrapers/` — flights, airbnb (browser-use)
- `tools/` — secrets, telemetry, model_router, db_context, airbnb_account, cost, report
- `api/` — FastAPI BFF (routes, middleware)
- `db/migrations/` — schema + Row-Level Security policies
- `tests/` — contract, integration, unit

## Deployment

`agent.yaml` is the Turing deployment block: services, GCP region/project
(PDPL/KSA data residency, constitution Principle XII), and the H2O-O graph —
the real agent/tool call graph, with node names matching `@traced`'s
`node_name` exactly so the graph and OTel spans never drift apart. When the
`h2o_substrate.sdk` migration lands (PRD §8.5), this graph is what its node
decorators wrap; business logic and the OTel attribute schema stay unchanged.

`BTM_DB_POOL_MIN`/`BTM_DB_POOL_MAX` (default 1/3, `tools/db_context.py`) size
the asyncpg pool — the small default exists so the test suite (which
re-inits the pool per test) never exhausts Postgres's connection limit. A
real deployment under concurrent tenant load should override both.

## Local development

```bash
cp .env.example .env  # fill in BTM_SESSION_SECRET, BTM_DATABASE_URL
pip install -e ".[dev]"
pytest
ruff check .
```

Run migrations in order: `0001_initial.sql`, `0002_rls.sql`, then `0003_app_role.sql`
(creates the `btm_app` role — set its password via `psql -v btm_app_password=...`,
never hardcode it).

Most tests run without a database. The ones that don't (`test_tenant_isolation.py`,
and any HTTP-level test that creates a real session) need `TEST_DATABASE_URL`
pointed at a Postgres instance with all three migrations applied, plus
`TEST_SEED_DATABASE_URL` pointed at a superuser/owner connection for fixture
setup — **these two must be different roles**. Row-Level Security never
applies to a superuser or table owner, so if `TEST_DATABASE_URL` is ever a
superuser connection, `test_tenant_isolation.py` will pass without proving
anything (this happened once during initial implementation — see
`db/migrations/0002_rls.sql`'s comment).

```bash
export TEST_DATABASE_URL=postgresql://btm_app:...@localhost:5432/btm_test
export TEST_SEED_DATABASE_URL=postgresql://postgres@localhost:5432/btm_test
pytest
```
