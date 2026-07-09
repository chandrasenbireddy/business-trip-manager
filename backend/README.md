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

## Local development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```
