# BTM validation checklist

_Source of truth for Aug 1 live-test fix priority. Work top to bottom._

## Live-test findings (Aug 1)

**No live agent should depend on local Ollama — remove the local dependency entirely, no fallback to local.**

### P0 — done

- [x] **P0 — Swap LLM provider off local Ollama.** NVIDIA NIM (`nvidia/nemotron-3-ultra-550b-a55b`) primary for all research/scraper LLM calls.
- [x] **P0 — Add a free-tier fallback provider.** Groq on NIM timeout / error / rate-limit; log serving provider + fallback reason.
- [x] **P0 — Make `POST /trips` research non-blocking.** Background task; scraper failures → `research_failed` (migration 0008). Live DEV_BYPASS: create hung 90–300s → ~7.8s.

### P1 — done (committed)

- [x] **P1 — Fix Airbnb scraper contract mismatch.** Parse `AgentHistoryList.final_result()` JSON into `list[dict]` for Airbnb and flights; empty/unparseable → raise (compatible with `research_failed`).
- [x] **P1 — Fix embeddings config contradiction.** NIM `nvidia/nv-embedqa-e5-v5` via `NVIDIA_API_KEY`; no key → `None` (recency-only); migration 0009 → `vector(1024)`; `store_turn` persists embedding.
- [x] **P1 — Close episodic sessions.** After confirm+booking, status `closed` + `closed_at=now()` so destination history / `retrieve_context` can find sessions.

### Gate: push + full lifecycle re-test

- [ ] Push `feature/001-btm-mvp` (3 commits through `6325e26`, plus this checklist gate commit).
- [ ] Full DEV_BYPASS Compose lifecycle: create → search → select → confirm → book (real endpoints, not mocks).
- [ ] Note: **P2 does not block this gate** — re-test and report findings only; do not implement P2 fixes here.

### P2 — pending (does not block gate)

- [ ] **P2 — Fix cost tracking.** `tokens_in/out` always 0.
- [ ] **P2 — Wire GCS for report sharing.** `share_url` returns null.
- [ ] **P2 — Refresh Airbnb cookie** (`cookie_status: expired`).

Full lifecycle re-test still blocked by live browser scrape quality, booking stubs, and P2 items above.
