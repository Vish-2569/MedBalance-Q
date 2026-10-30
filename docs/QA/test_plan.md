# MedBalance-Q Test Plan

## 1. Scope

This plan covers all testing activities for MedBalance-Q (Quant-A-Maze 3.0, GENAI-04), a district-level medicine redistribution system. Testing spans five layers:

| Layer | What | Tool |
|---|---|---|
| Unit | Pure functions, adapters, rules, math | pytest (per service) |
| Contract | Fixture JSON vs OpenAPI schema | pytest (contracts/) |
| Integration | Full-stack scenario walkthroughs (CP1, CP2) | pytest (tests/integration/) |
| E2E | Browser demo path through all 10 pages | Playwright (tests/e2e/) |
| AI Eval | Extraction, anomaly, narration, forecast, copilot gates | evals/run_evals.py |

### In scope
- All 9 microservices (core-api, ingest-ai, genai, forecast, optimizer, coldchain, sim-control, sim-hospital, sensors)
- Shared library (medbal_common: FEFO, audit, settings, db, bus)
- Web frontend (10 pages, SSE, copilot panel)
- QUBO solver chain (4 tiers), MILP baseline, Max-Cut zoning
- AI pipeline: extraction, anomaly gate, narration firewall, forecast context multiplier, copilot tool use
- Cold chain monitoring, custody chain, DTA voucher generation

### Out of scope
- Load testing at scale (> 20 plan iterations)
- Penetration testing
- Accessibility (WCAG) — deferred
- Multi-browser (Firefox, Safari) — Chromium only for demo

## 2. Approach

- **Unit tests** run in isolation with SQLite in-memory, FakeProvider, and USE_FIXTURES=1.
- **Contract tests** validate fixture JSON shapes against OpenAPI YAML specs.
- **Integration tests** (CP1, CP2) run against a live Docker Compose stack with seed 42.
- **E2E tests** run against Vite dev server in fixture mode (VITE_USE_FIXTURES=1) with Playwright Chromium.
- **AI evals** run offline (deterministic parsers + golden labels) or live (against genai gateway with GEMINI_API_KEY).

## 3. Environments

| Environment | Purpose | Config |
|---|---|---|
| Local (pytest) | Unit + contract tests | SQLite, USE_FIXTURES=1, no Docker |
| Docker Compose (full profile) | Integration tests | Postgres 16, Redis 7, Mosquitto 2, seed 42 |
| Vite dev server | E2E tests | VITE_USE_FIXTURES=1, Chromium headless |
| Docker Compose + GEMINI_API_KEY | Live AI evals | Full stack + LLM provider |

## 4. Entry criteria
- All service Dockerfiles build successfully (`make build`)
- Seed generation completes (`make seed`)
- Shared library tests pass (`cd libs/medbal_common && uv run pytest`)

## 5. Exit criteria
- All unit tests pass (≥ 299 tests across 37 files)
- All 24 contract tests pass
- CP1 (15 tests) and CP2 (14 tests) integration tests pass
- E2E demo path passes 3 consecutive runs (16 tests × 3 = 48 runs, 0 failures)
- AI eval gates: all 10 gates PASS (offline mode minimum)
- No P0 or P1 defects open

## 6. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| GEMINI_API_KEY unavailable | AI live evals skip | Offline eval mode with golden labels |
| Docker build cache miss | CI slow | Layer caching in py-base image |
| Flaky SSE timing | E2E false failures | Fixture mode bypasses SSE; generous timeouts |
| Leaflet tile load failure | Map test fails | SVG fallback + both marker types checked |
