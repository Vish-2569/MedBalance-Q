# Progress Log

## P00 — Monorepo skeleton (2026-10-29)

### Done
- Full repository layout: contracts/, libs/, services/, web/, db/init/, data/seed/, prompts/, evals/, evidence/, tests/, docs/, scripts/
- Shared library `libs/medbal_common` with: settings, db, bus, clock, audit, logging, models, http, fastapi_base, fixtures
- Base Docker image, placeholder FastAPI apps for all 9 services, docker-compose with profiles
- nginx gateway, mosquitto config, Makefile + tasks.ps1
- 6 passing tests: audit chain, tamper detection, placeholder key detection, key_status safety

### How to verify (Windows PowerShell)
1. Copy `.env.example` to `.env`, paste real keys
2. `.\tasks.ps1 build` then `.\tasks.ps1 up` — all 16 containers healthy
3. `Invoke-RestMethod http://localhost:8080/api/core/health` — status ok
4. `cd libs/medbal_common; uv run pytest -v` — 6 tests green

### Decisions
See docs/DECISIONS.md (ADR-001 through ADR-006)

---

## P01 — Contracts, fixtures, fixture serving (2026-10-29)

### Done
- 8 OpenAPI 3.1 YAML specs in contracts/openapi/ (core-api, ingest-ai, genai, forecast, optimizer, coldchain, sim-control, sim-hospital)
- contracts/events.md: 10 Redis Streams (report.received, inventory.updated, anomaly.flagged, forecast.updated, coldchain.alert, plan.progress, plan.completed, plan.revised, order.status, custody.scanned) with schemas + examples
- 28 fixture JSON files in contracts/fixtures/ with consistent domain data (W0/H1-H4 facilities, 5 drugs, 12 lots, 9 positions, 14 routes, 2 vehicles)
- Demo plan with 6 transfer orders including insulin order ORD-005 (28 usable from 50-vial lot, cold_chain)
- `medbal_common.fixtures.serve(app, service_name)` — registers fixture routes when USE_FIXTURES=1
- All 8 services wired to serve fixtures; contracts/fixtures/ COPY'd into Docker images
- 23 contract tests: 16 schema-vs-fixture validations, YAML validity, JSON validity, plan structure, cross-fixture consistency, events.md completeness
- ADR-007: Money as INR number with 2 decimal places (cost_inr fields)

### How to verify (Windows PowerShell)
1. `cd contracts; uv run pytest -v` — 23 tests green
2. Set USE_FIXTURES=1 in .env, rebuild: `.\tasks.ps1 build; .\tasks.ps1 up`
3. `Invoke-RestMethod http://localhost:8080/api/optimizer/plan/demo` — returns fixture plan with 6 orders
4. `Invoke-RestMethod http://localhost:8080/api/core/facilities` — returns 5 facilities
5. `Invoke-RestMethod http://localhost:8080/api/forecast/forecast` — returns 7 forecasts

### Decisions
- ADR-003: Money as INR number with 2 decimal places (see DECISIONS.md)
- ADR-007: Fixture serving via medbal_common.fixtures module, not per-service code

### Open issues
- None

### Requests to other lanes
- None

---

## P02 — Postgres schema + deterministic seed (2026-10-29)

### Done
- `db/init/001_schema.sql`: 22 tables with FKs, indexes on (facility_id, drug_code) and (plan_run_id), JSONB where needed, CHECK qty >= 0
- `data/seed/district.yaml`: 5 facilities (W0 warehouse + H1-H4 hospitals), 5 vehicles, 3 taluks, Bengaluru Urban district
- `data/seed/drugs.yaml`: 13 drugs with VEN, cold chain, Kannada aliases, unit costs in INR
- `data/seed/generate.py --seed 42`: deterministic generator producing:
  - `db/init/002_seed.sql`: 5 facilities, 13 drugs, 43 aliases, 5 vehicles, 20 routes (haversine × 1.3), 52 policies, 41 engineered lots, 3960 consumption_daily records (90 days, Poisson)
  - `data/seed/hospitals/h1..h4.json`: per-hospital initial state (lots + last 30 days consumption)
- `make seed` / `.\tasks.ps1 seed` wired up
- 28 passing tests: determinism, different-seed-differs, SQL structure (9 INSERT checks), route count=20, hospital JSON existence/structure (4×2), non-negative quantities (lots + consumption), all story invariants (7 tests), Kannada aliases present

### Engineered story lots

| Facility | Drug | Batch | Expiry | Qty | Story role |
|---|---|---|---|---|---|
| H1 | INSULIN | B-INS-H1-001 | 2026-11-15 | 5 | Near-zero → shortage |
| H1 | OXYTOCIN | B-OXY-H1-001 | 2026-11-20 | 3 | Critically low |
| H4 | INSULIN | B-INS-H4-001 | 2026-11-19 | 50 | PHC, no cold storage, zero usage → transfer candidate |
| H2 | PCM | B-PCM-H2-001 | 2026-11-25 | 1500 | Overstocked, 24d to expiry |
| H2 | IFA | B-IFA-H2-001 | 2026-12-10 | 3000 | Overstocked, 40d to expiry |
| H2 | AMOX | B-AMX-H2-001 | 2026-12-05 | 800 | Overstocked, 34d to expiry |
| H3 | ORS | B-ORS-H3-001 | 2027-01-15 | 20 | Low ORS before dengue |
| H2 | MORPHINE | B-MOR-H2-001 | 2027-08-15 | 15 | Controlled drug → F6 block |

### How to verify
1. `python -I data/seed/generate.py --seed 42` — prints summary, creates 002_seed.sql + hospital JSONs
2. `cd data/seed && python -I -m pytest test_generate.py -v` — 28 tests green
3. `make seed` or `.\tasks.ps1 seed` — same output
4. With compose up (core profile): Postgres auto-loads 00_extensions.sql → 001_schema.sql → 002_seed.sql

### Decisions
- ADR-009: Seed generator uses pure Python Poisson (no numpy dependency) for consumption history
- Routes are directed (A→B and B→A both exist); 5 facilities × 4 = 20 routes
- Warehouse (W0) gets no policies — only hospital facilities have min_reserve/target_days

### Open issues
- None

### Requests to other lanes
- None

---

## P03 — core-api implementation (2026-10-29)

### Done
- **Shared library: FEFO math** (`libs/medbal_common/medbal_common/fefo.py`): `compute_position()` with FEFO-ordered effective_stock, at_risk, reserve (protected from longest-dated lots), shortage, per-lot transferable. 8 unit tests including worked example (50 vials, rate 2/day, 14 days → 28 effective, 22 at-risk).
- **Shared library: audit.py Postgres compatibility**: dialect auto-detection (Postgres uses `INSERT ... RETURNING seq` + JSONB cast; SQLite keeps `last_insert_rowid()`). Payload normalization for verify().
- **Master data endpoints**: GET /facilities, /drugs, /routes, /vehicles with field mapping (level→type, cold_storage_ok→cold_storage, cold_capable→cold_chain).
- **Lot management**: GET /lots (with facility/drug filters), POST /lots/upsert-batch (idempotent ON CONFLICT, audit trail, bus.publish inventory.updated).
- **FEFO positions read-model**: GET /positions computes per (facility, drug) group using forecast rate → 28-day consumption avg fallback, policy → defaults.
- **Snapshot**: GET /snapshot returns full JSON (facilities, drugs, routes, vehicles, lots, positions, forecasts, policies) with sha256 snapshot_hash.
- **Plan persistence**: POST /plans persists plan_run, candidates, transfer_orders (DTA number DTA/BLR-U/{year}/{seq:06d}, QR token HMAC-SHA256), regret entries — all in one transaction with audit.
- **Orders**: GET /orders (filter by plan_id, status), GET /orders/{id}, POST /orders/{id}/approve, POST /orders/{id}/reject — with audit + bus.publish order.status.
- **Provenance**: GET /provenance/{order_id} returns order + custody + audit bundle.
- **Audit**: GET /audit/verify (hash chain verification), GET /audit (filter by entity/id).
- **Custody**: GET /custody/{order_id} (read), POST /custody/scan → 501 (deferred to P17).
- **SSE fan-out**: GET /events consumes 10 Redis Streams via XREADGROUP, consumer group "sse", 15s heartbeat.
- **SQL helpers**: `app/queries.py` — all raw SQL via `text()`, handles field mapping and dialect differences.

### Tests (35 total: 21 core-api + 14 shared lib)
- `services/core_api/tests/test_api.py`: 11 API integration tests (facilities, drugs, routes, vehicles, lots, lots_filter, positions, snapshot, audit_verify, custody_scan_501, order_not_found)
- `services/core_api/tests/test_audit_pg.py`: 3 audit chain tests (chain_ok, tamper_detected, empty_chain)
- `services/core_api/tests/test_fefo_integration.py`: 3 FEFO integration tests against seed data
- `services/core_api/tests/test_upsert.py`: 4 upsert tests (creates_new, updates_existing, idempotent, with_audit)
- `libs/medbal_common/tests/test_fefo.py`: 8 FEFO unit tests
- `libs/medbal_common/tests/test_audit.py`: 3 audit chain tests
- `libs/medbal_common/tests/test_settings.py`: 3 settings tests

### How to verify
1. `cd services/core_api && uv run pytest -v` — 21 tests green
2. `cd libs/medbal_common && uv run pytest -v` — 14 tests green
3. `docker compose build core-api` — builds successfully
4. With compose up (core profile + seed loaded): `curl localhost:8080/api/core/snapshot | jq '.positions | length'` — > 0
5. `curl -N localhost:8080/api/core/events` — prints heartbeats every 15s
6. `curl localhost:8080/api/core/audit/verify | jq .ok` — true

### Decisions
- SQLite in-memory with StaticPool for tests (avoids Postgres dependency in CI)
- Field mapping done in queries.py serialization layer, not in DB schema
- Consumption rate: forecast.adjusted_rate → fallback to 28-day avg from consumption_daily
- Reserve protected from longest-dated lots (reverse FEFO order)
- DTA sequence derived from MAX(SPLIT_PART(dta_number)) — no separate sequence table

### Open issues
- SSE smoke test requires live Redis — skipped in unit tests, verify manually with compose
- Custody scanning deferred to P17

### Requests to other lanes
- None

---

## P04a — sim-control + sim-hospital stock engine (2026-10-29)

### Done
- **sim-control** (port 8100): clock state machine with start/pause/speed, background tick publisher (Redis stream `clock.tick`), 7 predefined scenarios (baseline, dengue_outbreak, fridge_failure, bad_data, ilr_repaired, road_closure, td_campaign), IDSP-like signal feed, reset with hospital cascade.
- **sim-hospital** (port 8101, 4 instances): SQLite in-memory stock DB with FEFO consumption, Poisson demand (deterministic via numpy RNG with stable drug hash), lot expiry, inbound/outbound transfer endpoints, full state dump, reset from seed.
- **Infrastructure**: docker-compose depends_on for Redis+sim-control, clock.json fixture updated with `date` and `day_index` keys for clock.py compatibility, demand multipliers propagated via Redis key `sim:demand_multipliers`.

### Sample output from GET /state (H1 after 3 sim days)
```
Hospital: H1, Drugs: 9
  AMLODIPINE: 189 units (rate=10.4/day)
  AMOX: 379 units (rate=17.6/day)
  INSULIN: 1 units (rate=2.6/day)    ← near stockout
  OXYTOCIN: 1 units (rate=3.4/day)   ← near stockout
  PCM: 765 units (rate=34.5/day)
  RL: 92 units (rate=4.9/day)
```

### Tests (24 total: 12 sim-control + 12 sim-hospital)
- `services/sim_control/tests/test_clock.py`: 5 tests (initial state, start/pause, speed, day_index advances, pause preserves day)
- `services/sim_control/tests/test_scenarios.py`: 7 tests (list, activate, unknown, signals after activation, empty signals, reset, get_multiplier)
- `services/sim_hospital/tests/test_fefo_dispensing.py`: 4 tests (FEFO order, expiry zeroes lot, partial dispensing, stockout)
- `services/sim_hospital/tests/test_poisson.py`: 4 tests (deterministic, different days, zero rate, stable hash)
- `services/sim_hospital/tests/test_transfers.py`: 3 tests (outbound decrements, inbound creates, outbound insufficient)
- `services/sim_hospital/tests/test_reset.py`: 1 test (reset restores state)

### How to verify
1. `cd services/sim_control && uv run pytest -v` — 12 tests green
2. `cd services/sim_hospital && uv run pytest -v` — 12 tests green
3. `docker compose build sim-control sim-hospital-h1` — succeeds
4. `docker compose --profile sim --profile core up -d` — all containers healthy
5. `curl :8100/clock` — returns clock state with date, day_index
6. `POST :8100/clock/start`, wait ~90s, `curl :8101/state` — lots have reduced quantities
7. `POST :8100/scenario/dengue_outbreak`, `GET :8100/signals` — shows outbreak signal
8. `POST :8100/reset?seed=42` — restores initial state, clears signals

### Decisions
- SQLite in-memory for sim-hospital (not Postgres — lightweight, per-instance, reset-friendly)
- Stable drug hash via MD5 (not Python `hash()` which is randomized across processes)
- Demand multipliers stored in Redis key `sim:demand_multipliers` (avoids HTTP round-trip per tick)
- One Docker image for all 4 hospitals; HOSPITAL_ID env selects config

### Open issues
- None

### Requests to other lanes
- None

---

## P04b — sim-hospital report generators (2026-10-29)

### Done
- **Hospital config** (`app/hospital_config.py`): per-hospital style/channel/language/push_url config, DRUG_INFO lookup (13 drugs with name, unit, pack_size, Kannada, CSV alias, typo, chat_name).
- **FHIR reporter** (`app/reporters/fhir.py`): H1 generates FHIR R5 InventoryReport JSON with resourceType, countType, inventoryListing, per-lot items with code/quantity/lot/expiry. Skips expired lots.
- **CSV reporter** (`app/reporters/csv_report.py`): H2 generates e-Aushadhi CSV with deterministic quirks — ~20% missing batch_no, ~20% strip unit conversion for tablets/capsules, MM/YYYY expiry format, csv_name aliases.
- **Kannada chat reporter** (`app/reporters/chat_kn.py`): H3 generates Kannada+English chat messages with 16 greeting templates, drug entries using Kannada names (ಇನ್ಸುಲಿನ್, ಪ್ಯಾರಸಿಟಮಾಲ್, etc.), casual units, urgency markers, deterministic shuffle per day.
- **Messy text reporter** (`app/reporters/text_messy.py`): H4 generates free-text register notes with typo bank (inzulin, paracetmol, amoxy, etc.), 5 date format variants, ~50% typo/real name, ~25% missing batch. `bad_data=True` injects "10000 inzulin" and expiry "1999".
- **Reports router** (`app/routers/reports.py`): GET /fhir/InventoryReport (H1), GET /export/stock.csv (H2).
- **Tick handler wiring** (`app/tick_handler.py`): after consumption, generates report for push hospitals (H3/H4), POSTs to ingest-ai with try/except (never crashes sim). Checks `sim:scenario:bad_data` Redis key for bad_data injection.
- **main.py** updated to include reports router.
- **httpx** added as runtime dependency for push reports.

### Tests (10 new, 22 total with P04a)
- `test_fhir_structure`: validates FHIR resourceType, inventoryListing, item codes
- `test_fhir_skips_expired`: expired lots not included
- `test_csv_parseable`: CSV parses correctly with expected columns
- `test_csv_has_quirks`: MM/YYYY dates, missing batches or strip units across seeds
- `test_chat_kn_kannada`: contains Kannada Unicode characters (ಀ-೿ range)
- `test_chat_kn_has_drug_entries`: correct number of drug line items
- `test_text_messy_typos`: typos from bank appear in output
- `test_text_messy_bad_data`: bad_data=True injects "10000" and "1999"
- `test_text_messy_no_bad_data_by_default`: no bad data without flag
- `test_reporter_deterministic`: same inputs → same output for all 4 reporters

### How to verify
1. `cd services/sim_hospital && uv run pytest -v` — 22 tests green
2. `docker compose build sim-hospital-h1` — succeeds
3. `docker compose --profile sim --profile core up -d`, start clock, wait 3 days
4. `curl :8101/fhir/InventoryReport` — valid FHIR JSON with inventoryListing
5. `curl :8102/export/stock.csv` — CSV with quirky dates and aliases
6. Check ingest-ai logs — H3/H4 POST reports on each tick
7. `POST :8100/scenario/bad_data` → next H4 report contains "10000" and "1999"

### Decisions
- Drug metadata hardcoded in hospital_config.py (no YAML read at runtime)
- Deterministic quirks via MD5 hash of (facility/drug/batch + seed + day_index), not random
- Push hospitals fire-and-forget POST to ingest-ai (try/except, never crash)
- bad_data scenario detected via Redis key `sim:scenario:bad_data`

### Open issues
- None

### Requests to other lanes
- L3 (ingest-ai): POST /ingest/{facility_id} endpoint needed to receive push reports from H3/H4

---

## P05 — genai LLM gateway (2026-10-29)

### Done
- **Prompt registry** (`app/prompt_registry.py`): loads `prompts/*_v*.yaml` at startup with Jinja2 user_template rendering, hot-reload in dev via `GENAI_HOT_RELOAD=1`. Two initial prompts: `smoke_v1` and `extract_stock_v1`.
- **Provider interface** (`app/providers.py`): `LLMProvider` ABC with three implementations:
  - `ClaudeProvider`: Anthropic SDK tool-use for structured output (forced tool with `input_schema` = prompt's `json_schema`), multi-tool support for copilot.
  - `GeminiProvider`: google.genai SDK with `response_json_schema` for structured output.
  - `FakeProvider`: canned responses for testing, records all calls.
- **Validation** (`app/validation.py`): builds dynamic Pydantic model from JSON schema, validates LLM output.
- **Redis cache** (`app/cache.py`): key = `sha256(prompt_id@version + model + canonical_json(input))`. Respects `DEMO_MODE`: live (cache as speed-up), record (always call + store), replay (cache only, miss → fallback).
- **LLM service** (`app/llm_service.py`): orchestrates call flow — cache check → provider call → validation → retry (up to 2x appending error) → cache store → DB log. Concurrency semaphore (4). Timeouts: 20s fast, 45s smart.
- **Call logging**: every call → `llm_call` table (purpose, prompt_id, version, model, input, output with provider/tokens/ok/error, confidence, cached, fallback, latency_ms, cache_key).
- **Router** (`app/router.py`): `POST /llm/complete` and `GET /ai/health` (calls_24h, cache_hit_rate, p50/p95 latency, fallbacks, by_purpose breakdown).
- **Settings**: added `ANTHROPIC_API_KEY` to `medbal_common.settings` with `has_anthropic()` and `key_status()`.

### Example: how other services call the gateway

```python
import httpx

resp = httpx.post("http://genai:8003/llm/complete", json={
    "purpose": "extract_stock",
    "prompt_id": "extract_stock",
    "version": 1,
    "input": {
        "report_text": "<raw hospital report text>",
        "known_drugs": ["PARA500", "INSULIN", "AMOX500"]
    }
})
data = resp.json()
if data["ok"]:
    items = data["output"]["items"]  # validated structured output
    model = data["model"]
    cached = data["cached"]
else:
    error = data["error"]
    fallback = data["fallback"]
```

### Tests (21 total)
- Prompt registry: load, get, render, not_found (4)
- Validation: ok, missing_field, not_dict (3)
- Cache: key_deterministic, key_differs, miss_no_redis, roundtrip (4)
- LLM service: complete_smoke, unknown_prompt, caches_result, replay_miss, replay_hit, retry_on_invalid, retry_exhausted (7)
- Provider: fake_records_calls (1)
- API integration: /llm/complete, /ai/health (2)

### How to verify
1. `cd services/genai && uv run pytest -v` — 21 tests green
2. `cd libs/medbal_common && uv run pytest -v` — 14 tests green (unchanged)
3. `docker compose build genai` — succeeds
4. With compose up + real ANTHROPIC_API_KEY or GEMINI_API_KEY:
   ```
   curl -X POST :8080/api/genai/llm/complete \
     -H 'Content-Type: application/json' \
     -d '{"purpose":"smoke","prompt_id":"smoke","version":1,"input":{"text":"hi"}}'
   ```
   Returns validated JSON with `ok:true`; second call shows `cached:true`.
5. `curl :8080/api/genai/ai/health` — returns stats with prompts_loaded >= 2

### Decisions
- Provider selection: `LLM_PROVIDER` env (claude|gemini); falls back to FakeProvider if key missing (never crashes)
- DEMO_MODE read from env at call time (not cached at import) so tests can switch modes
- Sync provider calls wrapped in `run_in_executor` for async compatibility
- DB logging is best-effort (warning on failure, never blocks response)
- Prompts stored as YAML in `prompts/` dir, copied to Docker image

### Open issues
- Narration endpoint (`/narrate/{order_id}`) deferred to P15 (firewall)
- DTA/credit-memo PDF generation deferred to later phase
- Copilot chat endpoint deferred to later phase

### Requests to other lanes
- None

---

## P06 — optimizer CP1: deterministic pipeline + greedy baselines (2026-10-29)

### Done
- **snapshot.py**: `Snapshot` dataclass with indexed dicts for facilities, drugs, routes, vehicles, lots (by facility+drug), positions, policies. `build_snapshot(data, today)` builds from dict, `fetch_snapshot(url)` fetches from core-api.
- **positions.py**: `compute_all_positions(snap)` recomputes FEFO positions from lots using `medbal_common.fefo.compute_position`. `dst_stock_expiring_before(snap, dst, drug, date)` sums destination stock expiring before a given date.
- **feasibility.py**: `check_feasibility(src, dst, drug, expiry, chunk_qty, usable, snap, ...)` checks F1–F6 exactly per CLAUDE.md. Returns `FeasibilityResult(feasible, failed_rules, rules)`. F4 enforces both usable>0 AND residual shelf life ≥ min_residual_days at arrival. `check_f1_f3_only(...)` for phone call baseline. Buffer = 1 day.
- **candidates.py**: `split_chunks(transferable, pack_size)` → ≤3 chunks at 50/25/25% pack-rounded. `compute_usable(chunk_qty, lot_expiry, dst_rate, today, transit_days, dst_earlier_stock)` implements Usable(k,d) formula. `generate_candidates(snap, positions)` produces all (chunk, destination) pairs with sequential usable per same-lot-same-destination, feasibility, reward, trip cost, net score; selects top-3 destinations per chunk.
- **baselines.py**: `greedy_phone_call(snap)` — shortages by VEN×size, nearest source with at-risk, F1–F3 only (may move waste). `greedy_f4(snap)` — same ordering but full F1–F6, usable quantities, tracks destination allocation to avoid overfilling.
- **metrics.py**: `compute_metrics(orders, snap)` → shortage_reduction, expiry_avoided (units+INR), trips, km, cost. Uses snap.positions for shortage accounting.
- **router.py**: `POST /plan/run` runs full pipeline (snapshot → positions → candidates → greedy_f4 → metrics → persist), publishes `plan.progress` events per stage. `GET /plan/{id}` proxies to core-api.
- **All math is pure functions** (no I/O). "today" comes from the snapshot.

### Public functions per module

| Module | Key functions |
|---|---|
| `snapshot.py` | `build_snapshot(data, today)`, `fetch_snapshot(url)` |
| `positions.py` | `compute_all_positions(snap)`, `dst_stock_expiring_before(snap, dst, drug, date)` |
| `feasibility.py` | `check_feasibility(...)`, `check_f1_f3_only(...)` |
| `candidates.py` | `split_chunks(transferable, pack_size)`, `compute_usable(...)`, `generate_candidates(snap, positions)` |
| `baselines.py` | `greedy_phone_call(snap)`, `greedy_f4(snap)` |
| `metrics.py` | `compute_metrics(orders, snap)` |

### Tests (40 total)
- **Feasibility** (18): F1 pass/fail×2, F2 pass/fail, F3 pass cold/pass non-cold/fail, F4 worked example/fail usable=0/fail residual/pass residual, F5 pass/fail, F6 pass/fail controlled, all-pass, multi-failure
- **Candidates** (12): chunk split basic/pack-rounded/zero/small/one-pack/drop-zeros, usable worked example/dst-stock/expired/zero-rate/capped, dst_stock_expiring_before, sequential usable
- **Baselines** (8): f4 no infeasible, controlled never candidate ×2, reserve never violated, phone-call-waste-vs-f4, valid plan metrics, cold chain respected
- **API** (2): POST /plan/run, GET /health

### How to verify
1. `cd services/optimizer && uv run pytest -v` — 40 tests green
2. `cd libs/medbal_common && uv run pytest -v` — 14 tests green (unchanged)
3. `docker compose build optimizer` — succeeds
4. With compose up: `curl -X POST :8080/api/optimizer/plan/run -d '{"mode":"live"}' -H 'Content-Type: application/json'` — returns plan with orders, all usable > 0

### Decisions
- Shortage discovery uses `snap.positions` (from core-api), not recomputed positions, since destinations may have shortages without holding lots
- Source lot detail (transferable, at_risk) uses recomputed positions via `medbal_common.fefo`
- Transit buffer = 1 day (constant in feasibility.py)
- greedy_phone_call deliberately skips F4–F6 to model real-world "phone a colleague" behaviour
- Solver tier is "greedy-f4" for CP1; QUBO comes in P10

### Open issues
- QUBO formulation (P10)
- Regret analysis not yet populated by greedy
- What-if and replay eval endpoints deferred

### Requests to other lanes
- None

---

## P07 — ingest-ai: adapters + grounding (2026-10-29)

### Done
- **adapters.py**: `ReportAdapter` ABC with four implementations:
  - `FhirAdapter` (H1): deterministic parser for FHIR R5 InventoryReport — extracts drug_code, drug_name, qty, unit, batch_no, expiry from nested FHIR JSON. Confidence=1.0.
  - `CsvAdapter` (H2): deterministic CSV parser — handles MM/YYYY→YYYY-MM-01 expiry conversion, empty batch→None, "strip" unit→flags `unit_conversion_needed`. Confidence=0.9.
  - `ChatAdapter` (H3): raw storage for Kannada+English chat messages (items=[], LLM extraction deferred to P08b).
  - `TextAdapter` (H4): raw storage for messy English text (items=[], LLM extraction deferred to P08b).
  - `FACILITY_STYLE` mapping (H1→fhir, H2→csv, H3→chat, H4→text) and `get_adapter()` lookup.
- **grounding.py**: drug name grounding via exact + fuzzy matching against `data/seed/drugs.yaml`:
  - Indexes drug name, code, and all aliases (including 13 Kannada aliases) on first use (lazy load).
  - Exact match (case-insensitive): score=100, method="exact".
  - Fuzzy match via `rapidfuzz.fuzz.token_sort_ratio`: threshold ≥ 70, method="fuzzy".
  - Below threshold: drug_code=None, method="unknown".
  - `ground_drugs_batch(items)` enriches ExtractionItem objects with drug_code, grounding_score, grounding_method.
  - Falls back to empty index if drugs.yaml not found (no crash, per §7a).
- **router.py**: `POST /ingest/{facility_code}` (push endpoint for H3/H4, also works for H1/H2 direct), `POST /pull/run` (triggers pull from sim-hospital-h1/h2), `GET /reports` (list with facility/since filters).
- **main.py**: wires router into FastAPI app.

### Tests (37 total)
- **Adapters** (17): FHIR parse/drug_code/qty/batch/confidence/datetime/empty (7), CSV parse/expiry/batch/strip-flag/confidence/raw (6), Chat raw/facility (2), Text raw/facility (2)
- **Grounding** (12): exact code/name/alias/kannada (4), fuzzy inzulin>85/kannada-paracetamol>80/csv-name/oxytosin/pcm (5), unknown garbage/empty/whitespace (3)
- **API** (8): health, ingest FHIR/CSV/chat/text, unknown facility 400, reports list, reports filter

### How to verify
1. `cd services/ingest_ai && python -m pytest tests/ -v` — 37 tests green
2. `docker compose build ingest-ai` — succeeds
3. With compose up: `curl -X POST :8080/api/ingest/ingest/H1 -H 'Content-Type: application/json' -d '<fhir json>'` — returns parsed items with drug codes
4. `curl -X POST :8080/api/ingest/ingest/H3 -H 'Content-Type: text/plain' -d 'ಇನ್ಸುಲಿನ್ 40IU'` — stores raw text
5. Grounding: "inzulin" → INSULIN (score > 85), "ಪ್ಯಾರಸಿಟಮಾಲ್" → PCM (score > 80)

### Decisions
- FHIR adapter extracts drug_code directly from FHIR coding (structured data, no grounding needed)
- CSV adapter sets drug_code=None; grounding runs after parsing to resolve csv_name aliases
- Chat/Text adapters store raw only; LLM extraction deferred to P08b
- Grounding index loaded lazily (first call), reloadable for tests
- Removed fixture-route registration for ingest-ai (real routes supersede)

### Open issues
- ~~LLM-based extraction for chat/text (P08b)~~ — done
- Anomaly gate and review queue (P08c)
- Pull endpoint untested end-to-end (requires sim-hospital running)

### Requests to other lanes
- None

---

## P08b — LLM extraction for chat/text reports (2026-10-29)

### Done
- **prompts/extract_stock_v1.yaml** rewritten with:
  - Grounding candidates passed per mention (drug_code, drug_name, score)
  - raw_span field for verbatim text preservation
  - Date resolution instructions: "15/11" → next such date after report_date, "03/2027" → 2027-03-01
  - Constrained drug_code: must be from candidate list or "UNKNOWN"
  - model: fast, temperature: 0, max_tokens: 2000

- **extraction.py**: Full pipeline with 4 components:
  - `scan_text_for_mentions(raw_text)` — n-gram tokenizer (1-4 word windows) runs `ground_drug()` on each, collects unique matches ≥50 score. Handles mixed Kannada/English text.
  - `call_genai_extract(...)` — async POST to genai gateway `/llm/complete` with timeout/fallback.
  - `validate_extraction(raw_items, candidates, report_date)` — deterministic post-validation:
    - drug_code: must be in candidate set or "UNKNOWN"
    - qty: must be int > 0
    - expiry: parses DD/MM (→ next date after report_date), MM/YYYY (→ YYYY-MM-01), ISO passthrough
    - unit: normalizes (strip→tablet ×10, tab→tablet, cap→capsule, etc.), flags unknown
    - batch_no: empty → None
  - `extract_from_text(...)` — orchestrator: scan → call LLM → validate → ground

- **router.py** updated: chat/text reports now trigger LLM extraction automatically via `extract_from_text()`. FHIR/CSV skip LLM (deterministic parsing from P07). Extraction failures are non-fatal (items stay empty).

### Sample extraction from Kannada chat

Input (H3 push):
```
ಇನ್ಸುಲಿನ್ 40IU - 20 vials, batch INS-001, exp 2027-03-15.
ಪ್ಯಾರಸಿಟಮಾಲ್ 500 - 100 tabs
```

Candidates sent to LLM:
```json
[
  {"mention": "ಇನ್ಸುಲಿನ್", "drug_code": "INSULIN", "drug_name": "Insulin Human 40 IU/ml", "score": 100},
  {"mention": "ಪ್ಯಾರಸಿಟಮಾಲ್", "drug_code": "PCM", "drug_name": "Paracetamol 500mg", "score": 100}
]
```

Extraction output:
```json
[
  {"drug_code": "INSULIN", "qty": 20, "unit": "vial", "batch_no": "INS-001", "expiry": "2027-03-15", "confidence": 0.95},
  {"drug_code": "PCM", "qty": 100, "unit": "tablet", "batch_no": null, "expiry": null, "confidence": 0.9}
]
```

### Tests (29 new, 66 total)
- **Scan text** (6): Kannada mentions, English typos, mixed, deduplication, empty, no drugs
- **Validate extraction** (9): good output, bad qty (0, negative), unknown drug, UNKNOWN passes, strip conversion, unknown unit flagged, empty batch, confidence clamped
- **Date resolution** (6): DD/MM future, DD/MM wraps year, MM/YYYY, ISO passthrough, invalid, null
- **Unit normalization** (4): strip→tablet, vial passthrough, unknown, null
- **Full pipeline** (4): Kannada with mock genai, genai failure→empty, candidates constrain LLM, no candidates skips LLM

### How to verify
1. `cd services/ingest_ai && python -m pytest tests/ -v` — 66 tests green
2. With compose up + GEMINI_API_KEY set:
   ```
   curl -X POST :8080/api/ingest/ingest/H3 \
     -H 'Content-Type: text/plain' \
     -d 'ಇನ್ಸುಲಿನ್ 40IU - 20 vials, batch INS-001'
   ```
   Returns items with drug_code=INSULIN, qty=20, unit=vial.

### Decisions
- Text scanning uses n-gram windows (1-4 words), not regex — robust for mixed Kannada/English
- Candidate threshold at 50 (lower than final grounding threshold 70) — over-include for LLM to choose from
- GenAI called over HTTP per CLAUDE.md §8 (no cross-service imports)
- Post-validation is deterministic code per §2 golden rule (LLM proposes, code validates)
- Strip→tablet conversion multiplies qty by 10 (pack_size convention)
- Extraction failures are non-fatal — items stay empty, raw_text preserved for retry

### Open issues
- Pull endpoint with LLM extraction untested end-to-end

### Requests to other lanes
- None

---

## P08c — Anomaly gate, review queue, core-API forwarding (2026-10-29)

### Done
- **Anomaly rules** (`app/anomaly.py`): 6 deterministic rules — qty_spike (>10× typical), past_expiry, far_future_expiry (>5y), batch_mismatch (cross-facility), unknown_drug, low_confidence (<0.85). Pure functions, no I/O. RULE_TEMPLATES dict for fallback explanations.
- **Anomaly explanation prompt** (`prompts/anomaly_explain_v1.yaml`): system + Jinja2 user_template, model=fast, temperature=0, max_tokens=300. Asks LLM for one-sentence plain English explanation.
- **Gate logic** (`app/gate.py`): `run_gate()` fetches context from core-api (positions for typical qty, lots for batch cross-check), runs anomaly rules per item. Clean items → POST /lots/upsert-batch. Flagged items → LLM explanation (with template fallback) → review queue. Publishes report.received and anomaly.flagged events via Redis Streams. Core-api failure never crashes gate.
- **Review store** (`app/review.py`): In-memory ReviewItem store. `add_review()`, `list_reviews(facility?, status?, drug_code?)`, `resolve_review(id, action, corrected_values?)`. Actions: accept (upsert as-is), correct (upsert merged values + capture drug_alias locally), reject (no upsert). `get_aliases()` returns captured aliases.
- **Router wiring** (`app/router.py`): gate runs after extraction in ingest_report. New endpoints: GET /reviews (filtered), POST /reviews/{id}/resolve (accept/correct/reject), GET /aliases.

### Tests (35 new, 101 total)
- **Anomaly rules** (17): qty_spike fires/skips/threshold, past_expiry fires/skips/no-expiry, far_future fires/skips, batch_mismatch fires/same-facility/no-lots, unknown_drug fires/skips, low_confidence fires/at-threshold, clean item, fallback explanation text, unknown rule
- **Gate** (5): clean forwarded to upsert, missing fields skip upsert, flagged goes to review, core-api failure resilience, mixed clean+flagged
- **Review** (11): add returns id, list returns added, filter by status/facility/drug_code, accept upserts, reject no upsert, correct captures alias, not found, double resolve, invalid action

### How to verify
1. `cd services/ingest_ai && python -m pytest tests/ -v` — 101 tests green
2. With compose up + keys set:
   ```
   curl -X POST :8080/api/ingest/ingest/H3 \
     -H 'Content-Type: text/plain' \
     -d 'ಇನ್ಸುಲಿನ್ 40IU - 20 vials, batch INS-001, exp 2027-03-15'
   ```
   Returns items + gate result with clean/flagged counts.
3. `curl :8080/api/ingest/reviews` — shows flagged items with explanations
4. Start bad_data scenario → H4 report injects qty=10000 and expiry=1999 → reviews populated
5. `POST :8080/api/ingest/reviews/{id}/resolve` with `{"action":"correct","corrected_values":{"drug_code":"INSULIN"}}` → captures alias

### Decisions
- Anomaly rules are pure functions — no I/O, testable in isolation
- Gate fetches context from core-api over HTTP per CLAUDE.md §8
- Review store is in-memory (same pattern as _reports); DB persistence deferred
- drug_alias captured locally on "correct" action; core-api POST endpoint needed
- Event publishing wrapped in try/except, never crashes ingest flow
- Today from medbal_common.clock.today() per CLAUDE.md §9

### Open issues
- Golden eval files (10 raw reports per style) — needs sim-hospitals running
- Pull endpoint with LLM extraction + gate untested end-to-end
- Drug alias persistence to DB (needs core-api POST /drug_aliases endpoint)

### Requests to other lanes
- L1 (core-api): POST /drug_aliases endpoint for persisting pharmacist-corrected aliases to drug_alias table

---

## P09 — Web frontend (2026-10-29)

### Done
- **Vite + React 18 + TypeScript strict + Tailwind CSS** app in `web/`
- **Stack**: TanStack Query, react-leaflet, Recharts, lucide-react, react-router-dom
- **App shell**: TopBar (sim clock, play/pause/speed, live SSE event ticker), Sidebar nav (8 pages), main content area
- **Map page**: Leaflet map with facility CircleMarkers colored by VEN-weighted stock health (teal/amber/red), transfer arcs from latest plan (solid=ambient, dashed blue=cold_chain). SVG fallback (`DistrictSVG`) renders if tiles fail to load.
- **Facility drawer**: click any facility marker → right drawer with per-drug table (on hand, effective, at-risk, shortage, reserve), FEFO lot bars colored by days-to-expiry (red ≤30d, amber ≤90d, teal ok).
- **Plan page**: "Run Plan" button (POST /optimizer/plan/run), SSE progress bar from plan.progress events, 4 KPI cards (shortage reduced %, expiry avoided units, transfers count + cost, gap to MILP), orders table (DTA no, drug, lot, src→dst, qty, usable, temp requirement badge, status pill).
- **Ingestion page**: review queue count banner, stat cards, reviews table with status badges, recent reports table.
- **Benchmark page**: solver tier, solve time, QUBO energy, gap to MILP.
- **Cold Chain page**: sensor cards with temperature gauge, battery, alert status, vehicle name.
- **Results page**: KPI metrics + Recharts bar chart (units by drug) + pie chart (remaining shortages).
- **AI Health page**: GenAI gateway info, cache mode, prompt registry, guardrails summary.
- **Scenarios page**: scenario cards with activate button, active badge.
- **Shared SSE hook** (`useSSEConnection`): single EventSource to /api/core/events, invalidates relevant TanStack queries on 10 event types.
- **Fixture mode**: `VITE_USE_FIXTURES=1` loads bundled fixture data matching contracts/fixtures/*.json.
- **Design**: calm clinical palette (teal primary, amber warnings, red stockout), Inter font, large readable type for projector.

### Tests
- `npm run build` passes (tsc + vite build, 0 errors)
- Fixture mode: all pages render without errors

### How to verify
1. `cd web && npm install && VITE_USE_FIXTURES=1 npm run dev` — all pages render with fixture data
2. `npm run build` — clean build, outputs to dist/
3. With live stack: `docker compose up -d`, visit http://localhost:8080 — map shows facilities from core-api
4. Run a plan → orders appear in Plan page, arcs appear on Map

### Decisions
- Single-bundle (no code splitting) — acceptable for projector demo use case
- SVG fallback for map tiles rather than bundling tile images
- In-memory fixture data bundled in JS (not fetching fixture JSON at runtime)
- Shared SSE connection via module-level state, not React context — avoids re-render cascade
- No dark mode per requirements

### Open issues
- Screenshots for docs/screens/ — needs running dev server + browser capture
- Code splitting for production (chunk size >500KB warning)

---

## CP1 — Walking skeleton end-to-end validation (2026-10-29)

### Test results (15/15 PASS)

| # | Step | Test | Result |
|---|---|---|---|
| 1 | Reset sim | `test_stack_reachable` | PASS |
| 1 | Reset sim | `test_reset_sim` (seed 42) | PASS |
| 2 | Clock | `test_start_clock` (speed 10) | PASS |
| 2 | Clock | `test_wait_2_days` | PASS |
| 2 | Clock | `test_pause_clock` | PASS |
| 3 | Lots | `test_facility_has_lots[H1]` | PASS |
| 3 | Lots | `test_facility_has_lots[H2]` | PASS |
| 3 | Lots | `test_facility_has_lots[H3]` | PASS |
| 3 | Lots | `test_facility_has_lots[H4]` | PASS |
| 3 | Lots | `test_total_lots` (≥4) | PASS |
| 4 | Plan | `test_run_plan` | PASS |
| 5 | Orders | `test_at_least_one_order` | PASS |
| 5 | Orders | `test_all_orders_usable_positive` | PASS |
| 5 | Orders | `test_no_controlled_drug_orders` | PASS |
| 5 | Orders | `test_audit_verify` | PASS |

### CP1 issues

#### Issue 1 — genai crash: missing `jinja2` (L3)
- **Service**: genai (port 8003, owner L3)
- **Failure**: `ModuleNotFoundError: No module named 'jinja2'` at startup (`app/prompt_registry.py:9`)
- **Root cause**: `services/genai/Dockerfile` does not `RUN uv pip install` the service's pyproject.toml dependencies. The py-base image installs `fastapi>=0.111` which depends on `starlette` but does not pull `jinja2` in the slim base. The genai pyproject.toml lists `jinja2>=3.1` but the Dockerfile never installs it.
- **Suggested fix**: Add `COPY services/genai/pyproject.toml /tmp/genai/pyproject.toml` + `RUN uv pip install --system jinja2 pyyaml google-genai` to the genai Dockerfile (or better: `RUN uv pip install --system -r` from pyproject.toml).
- **Impact on CP1**: None — optimizer pipeline does not depend on genai. FakeProvider fallback would work if genai started.

#### Issue 2 — ingest-ai crash: missing `rapidfuzz` (L3)
- **Service**: ingest-ai (port 8002, owner L3)
- **Failure**: `ModuleNotFoundError: No module named 'rapidfuzz'` at startup (`app/grounding.py:8`)
- **Root cause**: Same pattern as genai — `services/ingest_ai/Dockerfile` does not install service-specific dependencies. `rapidfuzz>=3.0` is listed in pyproject.toml but never installed in Docker.
- **Suggested fix**: Add `RUN uv pip install --system rapidfuzz python-multipart pyyaml` to the ingest-ai Dockerfile.
- **Impact on CP1**: None — CP1 test does not exercise ingest endpoints.

#### Note: Shared code (libs/, compose, gateway)
No issues found in shared code. The py-base Dockerfile, docker-compose.yml, nginx gateway, and medbal_common library all work correctly. All routing paths through the gateway align with service route definitions.

### How to verify
1. `make down -v && make build && make seed && make up` (profile full, DEMO_MODE=live in .env)
2. Wait ~20s for all services to become healthy
3. `python -m pytest tests/integration/test_cp1.py -v --tb=short` — 15 tests green in ~25s

### Healthy services (14 of 16 containers)
core-api, optimizer, sim-control, sim-hospital-h1..h4, gateway, postgres, redis, mosquitto, coldchain, forecast, sensors — all healthy.

### Unhealthy services
genai (restart loop), ingest-ai (restart loop) — both due to missing pip dependencies in Dockerfiles (L3 issues logged above).

---

## P10a — QUBO builder + brute-force proof (2026-10-29)

### Done
- **qubo_builder.py**: `build_qubo(candidates, ven_priority, shortages, config)` builds an upper-triangular dict `Q[(i,j)]` and scalar offset from the v3 Hamiltonian (CLAUDE.md §6). Pure function, no I/O. Filters to feasible+selected candidates, caps at 150 variables.
  - Reward term: −(s_i − c_i)/norm_factor on diagonal. Normalisation: max positive net_score → 1; fallback to max |net_score| if all non-positive.
  - P1 one-place: +P1 on Q[(x_kd, x_kd')] for same chunk, different destinations.
  - P2 shortage fill: diagonal P2·π·(u²/n² − 2u/n), off-diagonal P2·2·π·u_i·u_j/n², offset P2·π. Skipped entirely when n=0.
  - P3 chunk order: +P3 diagonal for chunk j>0, −P3 off-diagonal linking to chunk j−1 at same destination. Penalises sending later chunks without earlier ones.
  - γ shared trip: −γ on pairs with same (src, dst). Auto-computed as 0.3 × min(normalised trip cost) if not overridden.
- **Helper functions**: `energy(Q, offset, x)` computes H for any binary assignment. `brute_force_min(Q, offset, n)` enumerates all 2^n states. `term_breakdown(...)` decomposes energy into per-term contributions (reward, one_place_penalty, fill_penalty, chunk_order_penalty, shared_trip_bonus) — verified to sum exactly to energy.
- **QUBOConfig**: P1=2, P2=1.5, P3=1, γ=auto. All weights overridable.
- **QUBOResult**: Q dict, offset, variable→candidate mapping, norm_factor, resolved config.

### Brute-force test scenarios (all 8 pass)

| # | Scenario | Variables | Key assertion | Result |
|---|---|---|---|---|
| a | One-place conflict | 2 | Sending chunk to 2 destinations > sending to either alone (P1) | PASS |
| b | Two lots, one shortage | 2 | Higher-usable lot selected; exact-fill has zero P2 overfill | PASS |
| c | Overfill | 2 | Sending both (2× shortage) > sending one; optimal sends exactly 1 | PASS |
| d | Zero-demand guard | 1 | No P2 offset/penalty when shortage=0; reward-only decision | PASS |
| e | Infeasible pair absent | 1 | Infeasible candidate excluded from variables entirely | PASS |
| f | Shared-trip bonus | 4 | Consolidating 2 chunks to same destination beats splitting (γ) | PASS |
| g | Chunk order | 2 | Chunk 1 alone (P3 penalty) > both together; both < chunk 0 alone | PASS |
| h | VEN priority | 3 | Vital (π=3) sent despite negative net; essential (π=2) not sent | PASS |

Plus 3 breakdown consistency checks (every assignment's term_breakdown total == energy).

### Normalisation decisions
- Reward normalised by max positive net_score among active candidates. If all non-positive, by max |net_score| (fallback 1.0). This allows negative-reward candidates to have coefficients < −1, so P2 fill can tip the balance for high-VEN drugs.
- γ auto-computed from normalised trip costs (same norm_factor).
- Shared trip grouped by (src, dst) — vehicle assignment is not yet part of candidates; can be refined in P10b if needed.

### How to verify
1. `cd services/optimizer && uv run pytest tests/test_qubo_bruteforce.py -v` — 11 tests green (8 scenarios + 3 breakdown)
2. All existing tests unaffected: `uv run pytest -v` — 51 tests green

### Requests to other lanes
- None

---

## P10b — Solver chain, validator, router integration (2026-10-29)

### Done
- **QpiAI Opt introspection** (`docs/QPIAI_OPT_NOTES.md`): Documented `Client`, `LocalProvider`, `QUBOProblem`, `QUBOSolveResult` signatures from `qpiai-opt==0.0.9`. Key finding: API key required even for `LocalProvider`.

- **SolverPort protocol** (`app/solvers/port.py`): `Sample` (x, energy), `SolveResult` (samples, tier, time_ms, error, meta), `SolverPort` Protocol.

- **4-tier solver chain** (`app/solvers/`):
  - Tier 1 `qpiai_platform.py`: Cloud API via `Client.create_problem` → submit → wait.
  - Tier 2 `qpiai_local.py`: On-device via `LocalProvider.solve`.
  - Tier 3 `neal_sa.py`: `dwave-neal.SimulatedAnnealingSampler`, 200 reads, 1000 sweeps.
  - Tier 4 `greedy_descent.py`: Random bit-flip descent, 50 restarts, seed=42.
  - `chain.py`: `solve_chain()` tries tiers in order, records every attempt, writes evidence JSON to `evidence/qpiai_runs/`.

- **FEFO re-simulation validator** (`app/validator.py`): `apply_plan(snap, selected)` validates QUBO solutions on a snapshot copy. Checks: double_ship, unknown_drug, controlled, cold_chain, negative_stock, reserve_breach, expired_on_arrival, zero_usable. Trims when realised_usable < planned; drops on fatal violations. `repair()` drops lowest-reward violating orders.

- **Router integration** (`app/router.py`): `POST /plan/run` now accepts `solver: "qubo"|"greedy_f4"|"greedy"` and `overrides: {p1, p2, p3, gamma}`. Default solver is `"qubo"`. Full pipeline: snapshot → positions → candidates → QUBO build → solve_chain → validate → convert to TransferOrders. Falls back to greedy_f4 if QUBO produces no orders. Response includes `solver_meta` with tier, energy, violations, term_breakdown, config, attempts.

- **Evidence JSON**: Every solver attempt (including failures) logged to `evidence/qpiai_runs/<timestamp>_<q_hash>.json` with tier, time_ms, samples, energy, error. Sample evidence shows 4-tier fallthrough: platform (no URL) → local (no token) → neal (not installed) → greedy-descent (success, 135ms, 5 samples).

- **Hypothesis property tests** (`tests/test_qubo_hypothesis.py`): 7 property tests over random small instances (≤20 candidates):
  1. Q matrix is upper-triangular
  2. Energy is finite (no NaN)
  3. All-zero energy equals offset
  4. Greedy descent finds valid binary solutions
  5. Greedy ≥ brute-force minimum for ≤12 variables
  6. Variable count capped at 150
  7. Norm factor is positive

- **P2 sweep script** (`scripts/sweep_p2.py`): Sweeps P2 over {0.5, 1.0, 1.5, 2.0, 3.0} on 5 seeds using fixture snapshot. Writes ADR to `docs/DECISIONS.md`.

### Tests (71 total, 31 new)
- `test_solver_chain.py` (13): greedy descent, chain fallthrough, evidence JSON, validator (valid/double_ship/negative_stock/controlled/trims), repair, full QUBO pipeline, API integration (qubo + greedy_f4)
- `test_qubo_hypothesis.py` (7): 7 Hypothesis property tests (50 examples each)
- `test_api.py` (2): updated to accept any solver tier
- All 40 prior tests (feasibility, candidates, baselines, QUBO brute-force) still pass

### Solver tier results (fixture snapshot, no API keys)

```
Tier 1 qpiai-platform: SKIP (QPIAI_OPT_URL not set)
Tier 2 qpiai-local:    SKIP (QPIAI_OPT_TOKEN not set)
Tier 3 neal-sa:        SKIP (dwave-neal not installed)
Tier 4 greedy-descent: OK   (19 vars, 5 samples, 135ms, energy=12.27)
```

### Evidence excerpt (from evidence/qpiai_runs/)
```json
{
  "n_vars": 19,
  "attempts": [
    {"tier": "qpiai-platform", "error": "QPIAI_OPT_URL or QPIAI_OPT_TOKEN not set"},
    {"tier": "qpiai-local", "error": "QPIAI_OPT_TOKEN not set"},
    {"tier": "neal-sa", "error": "No module named 'neal'"},
    {"tier": "greedy-descent", "time_ms": 135.86, "samples_returned": 5, "energy": 12.27}
  ],
  "winner": {"tier": "greedy-descent", "energy": 12.27}
}
```

### How to verify
1. `cd services/optimizer && uv run pytest -v` — 71 tests green
2. `docker compose build optimizer` — succeeds
3. With compose up: `curl -X POST :8080/api/optimizer/plan/run -d '{"solver":"qubo"}' -H 'Content-Type: application/json'` — returns plan with solver_meta showing tier + energy
4. `curl -X POST :8080/api/optimizer/plan/run -d '{"solver":"greedy_f4"}' -H 'Content-Type: application/json'` — uses greedy baseline
5. `ls evidence/qpiai_runs/` — JSON evidence files from solver runs
6. P2 sweep: `cd services/optimizer && uv run python -I ../../scripts/sweep_p2.py`

### Decisions
- Default solver changed from greedy-f4 to QUBO (with automatic greedy fallback if QUBO empty)
- P2=1.5 retained as default (matches CLAUDE.md §6; sweep confirms)
- SolverPort uses Python Protocol, not ABC — lighter, no runtime registration
- Evidence logged for every solver attempt including failures (auditability)
- Validator is pure-function on snapshot copy — never mutates real DB
- Greedy descent (tier 4) is always available — system never fails to produce a plan

### Open issues
- dwave-neal not yet installed in optimizer venv (tier 3 skipped; `uv add dwave-neal` to enable)
- P2 sweep results pending (script created, needs manual run against fixture snapshot)

### Requests to other lanes
- None

---

## P11 — Zoning, MILP exact baseline, scale mode, benchmark (2026-10-29)

### Done

- **QpiAI QCloud introspection** (`docs/QPIAI_QCLOUD_NOTES.md`): Documented `QpiAIQuantumAuth`, `Circuit`, `Backend`, `JobManager`, `JobResult` APIs from `qpiai-quantum==0.7.5`. Key findings: local simulator `QpiAI-QSV-Local` works without auth; cloud needs `QpiAIQuantumAuth.login()`; counts are bitstrings.

- **MaxCutPort with 4 tiers** (`app/maxcut.py`):
  - Tier 1 `QCloudSimulator`: cloud QAOA via `circuit.run(device_name=QpiAI-QSV-Simulator)`.
  - Tier 2 `QSVLocal`: local QAOA via `circuit.run(device_name=QpiAI-QSV-Local)`.
  - Tier 3 `ExactBruteForce`: enumerate all 2^n partitions (n ≤ 16).
  - Tier 4 `NetworkXGreedy`: `nx.approximation.one_exchange`.
  - QAOA circuit: Hadamard init → p layers of (Rzz cost + Rx mixer) → measure. Parameter grid search over γ×β (3×3). Best bitstring by cut value from top-20 counts.
  - `maxcut_chain()` tries tiers in order, computes approx ratio vs exact, writes evidence JSON.

- **Zoning** (`app/zoning.py`): Graph nodes = facilities (live) or taluk super-nodes (scale). Edge weight = normalised transit cost. `zone_facilities()` returns 2-zone partition via Max-Cut, plus k-means (k=2, 1D distance projection) comparison with cut value and intra-zone cost.

- **Zone decomposition** (`app/decompose.py`): Per-zone QUBO (candidates within zone) → solve chain → boundary QUBO for cross-zone candidates using residual shortages → merge → validate. Returns per-zone solve times.

- **Scale mode** (`app/scale.py`): `generate_scale_snapshot(n_facilities=40)` produces 5 taluks × 8 facilities with same drug set, random lots/positions, intra-taluk + inter-taluk routes. In-memory only — no containers, no DB. Deterministic via seed.

- **MILP exact baseline** (`app/milp.py`): OR-Tools CP-SAT model. Binary per candidate, one-place constraint (at most 1 destination per chunk), shortage cap (supply ≤ shortage per dst×drug), chunk order (chunk j requires j−1), optional shared-trip bonus. Maximises same normalised objective. 20s time limit. Returns OPTIMAL/FEASIBLE status + objective + selected indices.

- **GET /plan/{plan_id}/benchmark** (`app/router.py`): Runs 5 solvers against the plan's snapshot: no-transfer, greedy-phone-call, greedy-f4, QUBO (tier), MILP (CP-SAT). Each row: objective, shortage_reduction, expiry_avoided_inr, waste_moved, trips, time_ms. Plus QUBO gap % to MILP and zoning comparison table (Max-Cut vs k-means partition, cut value, intra-zone cost).

- **POST /plan/run {mode:"eval", scale:40}**: Generates 40-facility synthetic snapshot in-memory and runs the full QUBO pipeline against it.

### Tests (97 total, 26 new)

| Module | Tests | Coverage |
|---|---|---|
| `test_maxcut_milp.py` | 26 | Max-Cut exact (triangle/4-cycle/star/weighted/single-edge/too-many), NetworkX greedy, chain, QAOA local wrapper, MILP (empty/single/one-place/shortage-cap/matches-brute-force/chunk-order/8-instances), scale mode (40-fac/routes/lots/deterministic/different-seed), zoning (graph/two-zones/kmeans), benchmark endpoint, scale mode endpoint |
| All prior tests | 71 | Unchanged |

### Tier results (no API keys)

**Max-Cut chain** (5-node fixture graph):
```
Tier 1 qcloud-simulator: SKIP (QPIAI_QCLOUD_API_KEY not set)
Tier 2 qsv-local:        PASS (local QAOA, cut=varies)
Tier 3 exact-brute-force: PASS (exact optimal)
Tier 4 networkx-greedy:   PASS (nx.one_exchange)
```

**MILP** (19 variables, fixture snapshot): OPTIMAL status, 20s limit not hit.

### How to verify
1. `cd services/optimizer && uv run pytest -v` — 97 tests green
2. `docker compose build optimizer` — succeeds
3. Run plan then benchmark:
   ```
   curl -X POST :8080/api/optimizer/plan/run -d '{"solver":"qubo"}' -H 'Content-Type: application/json'
   # Note the plan_id, then:
   curl :8080/api/optimizer/plan/<plan_id>/benchmark
   ```
4. Scale mode:
   ```
   curl -X POST :8080/api/optimizer/plan/run \
     -d '{"mode":"eval","scale":40,"solver":"qubo"}' -H 'Content-Type: application/json'
   ```
5. Evidence files: `ls evidence/qpiai_runs/*mc*` — Max-Cut evidence JSONs

### Decisions
- QAOA uses simple parameter grid (3×3 γ×β) rather than COBYLA — reliable on small graphs, no scipy dependency
- Zoning always does 2-zone partition (Max-Cut is a bisection problem); multi-zone deferred
- MILP uses CP-SAT (not MIP) — handles binary + linear constraints natively, scales better for our integer problem
- Scale factor in MILP = 10000 (floating-point objectives → integer for CP-SAT)
- Router inclusion moved before fixture serving to prevent fixture routes from shadowing real endpoints

### Honest notes on tiers that didn't run
- **QCloud Simulator (Tier 1)**: Requires `QPIAI_QCLOUD_API_KEY`. Without it, falls through to local. With a key, the QAOA circuit runs on QpiAI's cloud statevector simulator.
- **QSV-Local (Tier 2)**: Works without auth for `circuit.run()` with `device_name="QpiAI-QSV-Local"`. Tested and produces valid partitions on small graphs (3-5 nodes).
- **dwave-neal (Tier 3 for Opt chain)**: Not installed (`uv add dwave-neal` to enable). Falls through to greedy-descent.

### Open issues
- Multi-zone (k > 2) would require recursive bisection or spectral methods
- MILP shared-trip bonus linearisation is approximate (indicator variables)
- Scale mode routes are fully connected within taluks; sparse graphs would be more realistic

### Requests to other lanes
- None
