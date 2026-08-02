# BTM validation checklist

_Source of truth for Aug 1 live-test fix priority. Work top to bottom._

## Live-test findings (Aug 1)

**No live agent should depend on local Ollama — remove the local dependency entirely, no fallback to local.**

### P0 — done

- [x] **P0 — Swap LLM provider off local Ollama.** NVIDIA NIM (`nvidia/nemotron-3-ultra-550b-a55b`) primary for all research/scraper LLM calls.
- [x] **P0 — Add a free-tier fallback provider.** Groq on NIM timeout / error / rate-limit; log serving provider + fallback reason.
- [x] **P0 — Make `POST /trips` research non-blocking.** Background task; scraper failures → `research_failed` (migration 0008). Live DEV_BYPASS: create hung 90–300s → ~7.8s.

### P1 — active / next

- [ ] **P1 — Fix Airbnb scraper contract mismatch.** `browser_agent.run()` doesn't return `list[dict]`; fix parsing for Airbnb and flights if shared.
- [ ] **P1 — Fix embeddings config contradiction.** Wire real embeddings (prefer NIM / `NVIDIA_API_KEY`); fix no-op/raise logic.
- [ ] **P1 — Close episodic sessions.** Set `closed_at` / close status so episodic retrieval works. No shared-memory cross-agent work.

### P2 — later (do not start until P1 done)

- [ ] **P2 — Fix cost tracking.** `tokens_in/out` always 0.
- [ ] **P2 — Wire GCS for report sharing.** `share_url` returns null.
- [ ] **P2 — Refresh Airbnb cookie** (`cookie_status: expired`).

Do not re-run full lifecycle until P0+P1 unblock search/select/confirm/book.
