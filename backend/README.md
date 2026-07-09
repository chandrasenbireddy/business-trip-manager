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

### Model routing

`models.yaml` + `tools/model_router.py` — NVIDIA NIM is the primary provider
for orchestrator/planner/booking/memory (`NVIDIA_API_KEY`); Groq is
orchestrator's only fallback today, for when NIM's free tier hits its 40
req/min cap (`GROQ_API_KEY`). The flights/Airbnb scrapers (browser-use) route
to a local Ollama vision model (`gemma4:12b`) instead — no API key, but
`ollama serve` with that model pulled must be running locally. Swapping any
role's model/provider is a `models.yaml` edit, never a code change.

## Local development

```bash
cp .env.example .env  # fill in BTM_SESSION_SECRET, BTM_DATABASE_URL, NVIDIA_API_KEY, GROQ_API_KEY
pip install -e ".[dev]"
pytest
ruff check .
```

Set `DEV_BYPASS=true` in `.env` to skip the session-cookie/waitlist/OAuth
onboarding flow entirely and hit any endpoint immediately as a fixed
dev-tenant admin (`api/middleware/auth.py`) — useful for exercising `/trips`
etc. without running the invite → approve → Google consent dance first.
Requires the exact string `"true"`; never set this anywhere near a real
deployment (there is no runtime check beyond that — see the comment next to
it in `.env.example`).

**Gotcha**: `browser_use` (a `scrapers/` dependency) calls `load_dotenv()` at
its own import time, which happens the first time anything in the process
imports `api.main` — this pulls whatever's in your local `.env` into
`os.environ` for the rest of that process, including `DEV_BYPASS` if you've
set it. `tests/conftest.py` forces that import and clears `DEV_BYPASS` at
collection time specifically so a local dev `.env` can't silently change
what the test suite authenticates as; if you add another env var here that
tests should never inherit from a real `.env`, clear it there too.

Run every migration in order: `0001_initial.sql` … `0006_shareable_reports.sql`.
`0003_app_role.sql` creates the `btm_app` role (set its password via
`psql -v btm_app_password=...`, never hardcode it) and grants it privileges
on every table that exists *at that point* — any later migration that adds a
table (e.g. `0006`) must include its own `GRANT ... TO btm_app` line, or the
app role gets `InsufficientPrivilegeError` on a table RLS otherwise allows it
to use.

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
