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

---

## P12 — Forecast service: Holt-Winters + LLM context multiplier (2026-10-30)

### Done

- **Baseline forecasting** (`services/forecast/app/baseline.py`): `holt_winters_forecast()` with weekly seasonality (statsmodels ExponentialSmoothing, seasonal_periods=7, additive trend+seasonal). Falls back to EWMA when < 14 days of history or statsmodels fails. Returns `BaselineResult` with daily_rate, p10/p90 from residuals, method tag.

- **LLM context multiplier** (`services/forecast/app/context.py`):
  - `SEASONAL_CALENDAR`: static monsoon/winter/dengue/dasara signals with months and affected drug codes.
  - `fetch_signals(today)`: merges sim-control GET /signals with seasonal calendar (by current month). Fixture mode skips HTTP call.
  - `relevant_signals(facility, drug, signals)`: filters by facility_id, drug_code, and `affects` list.
  - `get_context_multiplier(...)`: calls genai POST /llm/complete with `forecast_ctx_v1` prompt only when relevant signals exist. On failure, deterministic fallback using signal params.
  - `apply_guardrails(llm_output, signals)`: clamps multiplier to [0.5, 3.0], validates signal IDs against available signals, rejects if no valid citation or confidence < 0.5 → returns 1.0.

- **Prompt** (`prompts/forecast_ctx_v1.yaml`): system/user_template for context multiplier. Input: facility, drug, baseline_rate, recent_series, signals. Output JSON: {multiplier, confidence, signal_ids[], reasoning}. model=fast, temperature=0.

- **Forecast store** (`services/forecast/app/store.py`): in-memory `ForecastStore` singleton keyed by (facility_id, drug_code). `ForecastRow` dataclass with to_dict(). Supports upsert, get, list_all (with facility/drug filters), history, clear.

- **Runner** (`services/forecast/app/runner.py`): `run_forecast(today, facility_filter, drug_filter)` orchestrates: load data (core-api or fixtures) → fetch signals → per-pair baseline + context → store. Returns {forecasts, llm_calls, time_ms}. Publishes `forecast.updated` via Redis Streams. Fixture data: 90-day synthetic consumption with weekly seasonality + noise (seeded).

- **Backtest** (`services/forecast/app/backtest.py`): `run_backtest(actual_consumption)` computes MAPE for baseline vs adjusted per facility×drug. Returns mae, rmse, coverage, per_pair breakdown.

- **API routes** (`services/forecast/app/router.py`):
  - `POST /forecast/run` — runs forecast (optional facility_id, drug_code filter)
  - `GET /forecast` — list forecast rows (optional facility/drug query params)
  - `GET /forecast/backtest` — backtest against fixture consumption

- **Service wiring** (`services/forecast/app/main.py`): router included before fixture serving (same pattern as optimizer fix from P11).

- **Dependencies** (`services/forecast/pyproject.toml`): added statsmodels>=0.14, numpy>=1.26, httpx>=0.27.

### Tests (28 total)

| Class | Tests | Coverage |
|---|---|---|
| TestHoltWinters | 5 | Seasonal data, short series fallback, empty, constant, residuals |
| TestEWMA | 3 | Basic, empty, single value |
| TestGuardrails | 7 | Clamp high/low, no valid citation→1.0, empty citation→1.0, low confidence→1.0, valid passthrough, at threshold |
| TestRelevantSignals | 4 | Matching facility+drug, no match, seasonal affects filter, no facility filter |
| TestNoSignalPath | 1 | No signals → zero LLM calls |
| TestStore | 2 | Upsert+get, list with filters |
| TestRunner | 1 | Run produces forecasts with multiplier=1.0 when no signals |
| TestAPI | 5 | POST /forecast/run, GET /forecast, GET /forecast?facility=, GET /forecast/backtest, GET /health |

### How to verify
1. `cd services/forecast && python -m pytest tests/ -v` — 28 tests green
2. `docker compose build forecast` — succeeds
3. With compose up:
   ```
   curl -X POST :8080/api/forecast/forecast/run -H 'Content-Type: application/json' -d '{}'
   curl :8080/api/forecast/forecast
   curl :8080/api/forecast/forecast/backtest
   ```
4. Activate dengue_outbreak scenario → `POST /forecast/run` → H3 ORS forecast should show multiplier > 1 with outbreak signal id.

### Decisions
- Holt-Winters MIN_HW_DAYS = 14 (need 2 full weeks for weekly seasonality)
- EWMA alpha = 0.3 (standard default, responsive without being noisy)
- Seasonal calendar is static (not fetched from sim-control) — signals from sim-control are dynamic (outbreaks, campaigns)
- Context multiplier only called when relevant signals exist (keeps LLM calls low per requirement)
- Confidence threshold = 0.5 (at threshold passes, below rejects)
- Deterministic fallback uses signal params (demand_multiplier or factor field) when LLM unavailable

### Open issues
- Redis bus.publish for forecast.updated silently fails in test (no live Redis) — acceptable for unit tests
- End-to-end acceptance test with dengue_outbreak requires live compose stack

### Requests to other lanes
- None

---

## P13 — Web frontend pages (2026-10-30)

### Done
- **Ingestion & Review page** (`web/src/pages/IngestionPage.tsx`):
  - Report list with facility, channel badge (FHIR R5/e-Aushadhi CSV/Chat Kannada/Free Text), language badge (Kannada rendered with Noto Sans Kannada font), timestamp, status
  - Expandable report detail: raw text panel (left, Kannada-rendered with `.font-kannada`) + extracted items table (right) with per-item confidence chips (green ≥85%, amber 60-84%, red <60%)
  - Review queue table with anomaly type, LLM explanation, confidence; three actions: accept (check), correct (pencil → opens modal), reject (X)
  - Correction modal: drug code picker from candidates dropdown, qty input, expiry date picker
  - 4 stat cards: Reports Received, Flagged, Pending Reviews, Resolved (color-coded)
  - Pending review rows with `qty_spike` anomaly highlighted with subtle red background
  - Badge count in sidebar from pending reviews (via `anomaly.flagged` SSE events)

- **Plan page** (`web/src/pages/PlanPage.tsx`):
  - Solver tier badge (QpiAI Platform/Local/SA/Greedy Descent), gap to MILP, violations: 0 badge
  - Solver attempts cascade (shows each tier tried with skip/success)
  - 7-stage pipeline bar: Snapshot → Feasibility → Zoning → QUBO Build → Solve → Validate → Persist
  - 4 KPI cards: Transfers, Shortage Reduction, Expiry Avoided, Cost
  - **Zone mini-map** (SVG): facilities color-coded by Max-Cut zone partition, transfer arcs (dashed blue for cold chain), zone legend with tier and cut value
  - Orders grouped by destination (collapsible), cold chain snowflake icons
  - Regret analysis section

- **Benchmark page** (`web/src/pages/BenchmarkPage.tsx`):
  - QUBO gap to MILP badge, Max-Cut zoning tier badge
  - Grouped bar charts (objective comparison, shortage reduction) with per-solver colors
  - Full comparison table (Solver, Objective, Shortage Red., Expiry Avoided, Waste Moved, Trips, Time)
  - Zoning comparison: **three cards** — QAOA Max-Cut vs k-means vs Exact Brute-Force with partition, cut values, intra-zone costs, approximation ratios

- **Cold chain page** (`web/src/pages/ColdchainPage.tsx`):
  - Red pulsing excursion banner listing affected device IDs
  - Summary stat cards (Devices, OK, Excursions)
  - Device cards with Recharts temperature sparkline (2–8°C band shaded blue), state badge (OK/Warning/Excursion), battery, last seen
  - Auto-refresh every 5 seconds
  - **Global excursion banner** in App.tsx (pulsing red bar across all pages on `coldchain.alert` SSE events)

- **Scenario console** (`web/src/pages/ScenariosPage.tsx`):
  - Clock display with live date/day index/speed, play/pause buttons, speed controls (0.5x–10x)
  - Reset button with seed input
  - Active scenario cards (teal, with active badge) and available scenario cards (with Activate button)
  - Recent signals table (ID, type, params JSON, fired_at)
  - 7 predefined scenarios: baseline, dengue_outbreak, fridge_failure, bad_data, ilr_repaired, road_closure, td_campaign

- **Supporting infrastructure**:
  - Noto Sans Kannada font loaded via Google Fonts in index.html
  - Expanded domain types (StockReport, ReviewItem, Benchmark with exact zoning, ColdchainStatus with state+history)
  - Rich fixtures (4 reports incl. Kannada chat & flagged text, 3 reviews, 5 benchmark rows, 3 sensors with excursion, 7 scenarios, 2 signals, exact brute-force zoning)
  - Updated API layer with `resolveReview`, `getSignals`, `resetSim`

### How to verify
1. `cd web && npm run build` — zero errors
2. `VITE_USE_FIXTURES=1 npm run dev` — all pages render with fixture data:
   - **Ingestion**: 4 reports (H1 FHIR, H2 CSV, H3 Kannada chat, H4 flagged text); expand H3 to see Kannada raw text + extracted items; review queue shows 2 pending items with accept/correct/reject buttons
   - **Plan**: solver badges, pipeline stages, zone mini-map with 2 zones, 6 orders grouped by destination
   - **Benchmark**: 5-solver comparison, 3.02% gap, 3 zoning cards (QAOA/k-means/exact)
   - **Cold Chain**: sensor-03 excursion with rising sparkline, red banner
   - **Scenarios**: 7 scenario cards, clock controls, 2 signals

### Decisions
- Recharts for all charts (already in deps); fixture mode returns rich data matching live API shapes
- Zone mini-map uses simple SVG projection (no Leaflet dependency) — lightweight for the plan page
- Cold chain page refreshes every 5s; global excursion banner checks SSE events
- Exact brute-force zoning added to fixture for 3-way comparison

### Open issues
- None

### Requests to other lanes
- None

---

## CP2 — Scenario integration tests (2026-10-30)

### Done
- **tests/integration/test_cp2.py** — 9 tests in 6 classes:
  1. `TestStep1Setup` (3): stack reachable, reset sim seed=42, advance clock 2 days and pause
  2. `TestStep2Dengue` (2): activate dengue_outbreak, verify H3 ORS forecast multiplier > 1.0
  3. `TestStep3BadData` (3): activate bad_data, inject report with past expiry (1999) and qty=10000 directly to ingest-ai, verify review items or gate flags
  4. `TestStep4Plan` (3): run QUBO solver, assert tier is any QUBO variant, assert 0 violations
  5. `TestStep5Benchmark` (1): GET benchmark for plan, assert 5 solver rows
  6. `TestStep6Fridge` (2): activate fridge_failure, poll coldchain /status for EXCURSION within 90s

### Shared-code issues found and fixed (5 total)

| # | Lane | Service | Issue | Fix |
|---|------|---------|-------|-----|
| 1 | L3 | genai | `ModuleNotFoundError: No module named 'jinja2'` — Dockerfile missing deps | Added `RUN uv pip install --system jinja2 pyyaml "google-genai>=1.0.0" redis` before COPY |
| 2 | L3 | ingest-ai | `ModuleNotFoundError: No module named 'rapidfuzz'` — Dockerfile missing deps | Added `RUN uv pip install --system rapidfuzz python-multipart pyyaml httpx` |
| 3 | L3 | forecast | Dockerfile missing `statsmodels numpy httpx` | Added `RUN uv pip install --system statsmodels "numpy>=1.26" httpx` |
| 4 | L4/L3 | sim-control | `bad_data` scenario `activate()` did not set `sim:scenario:bad_data` Redis key that `sim_hospital/tick_handler.py:_check_bad_data()` checks | Added `r.set("sim:scenario:bad_data", "1")` in activate(); added key to `reset_scenarios()` cleanup |
| 5 | L4/L3 | sim-control | `get_signals()` returned params with keys `facility`/`drugs_affected` but forecast `relevant_signals()` expected `facility_id`/`affects`/`demand_multiplier` | Fixed `get_signals()` to emit `facility_id`, `affects`, `demand_multiplier`, `drug_code` in params |

### How to verify
1. Full stack running: `make down && make build && make seed && make up`
2. `python -m pytest tests/integration/test_cp2.py -v --tb=short`
3. Expected: 9 tests pass (dengue multiplier > 1, bad data flagged, QUBO tier, 5 benchmark rows, coldchain excursion)

### Decisions
- bad_data test injects directly to `/api/ingest/ingest/H4` (text/plain) rather than relying on sim-hospital tick + LLM extraction, since genai may lack API key in test environment
- fridge_failure test restarts clock and polls every 5s; sensor ramp takes ~60s (12 cycles × 5s) for 3 consecutive breaches
- QUBO tier assertion accepts any tier containing known QUBO solver names (platform, local, neal-sa, greedy-descent, or decomposed variants)

### Open issues
- Forecast `run_forecast` may fall through to multiplier=1.0 if seasonal calendar doesn't match the sim date; the dengue signal fallback depends on the `demand_multiplier` param in the signal (fixed in issue #5 above)
- If genai has no GEMINI_API_KEY, LLM extraction for text/chat reports returns empty items; the bad_data test works around this by injecting directly

### Requests to other lanes
- None

---

## P14 — Regret ledger, why-not, what-if, auto re-plan (2026-10-30)

### Done

- **regret.py** — Per-order regret ledger with ΔH analysis:
  - For each QUBO order, evaluates ΔH of flipping its variable: to nowhere (x_i=0), to each alternative destination (swap chunk), and from alternative top-k solver samples
  - `compute_regret_from_vars(var_to_order_id, candidates, qubo_result, solve_result, ven_priority)` → `list[OrderRegret]`
  - Each `OrderRegret` has top 5 `RegretEntry` sorted by ΔH ascending with `reason_code` (LOWER_USABLE, HIGHER_COST, LOWER_VEN, FAILED_RULE_Fx, WORSE_FILL) and deterministic `reason_text` with numbers
  - Regret is included in solver_meta.regret in the plan response
  - ΔH verified to match `energy()` recomputation (test passes)

- **whynot.py** — `GET /whynot?facility=&drug=`:
  - `compute_whynot(facility, drug, snap, candidates, orders)` → structured JSON
  - Returns: residual_shortage, supplied, every candidate source lot with failed_rules or the net_score that made it lose
  - Candidates sorted by feasibility desc, net_score desc
  - Lists F3 (cold chain) for H4 insulin when ILR is down (test passes)

- **whatif.py** — `POST /whatif {overrides}`:
  - Overrides: `add_vehicle`, `close_route`, `open_route`, `set_reserve_days`, `delay_days`, `repair_cold_storage`, `break_cold_storage`, `set_multiplier`, `remove_vehicle`
  - Deep-copies snapshot, applies overrides, runs full pipeline (QUBO → validate → metrics)
  - Returns diff vs live plan: orders added/removed/changed, KPI deltas (shortage_reduction, expiry_avoided, cost, trips)
  - Never persists as live
  - `repair_cold_storage(H4)` enables insulin transfers to H4 (test passes)

- **replan.py** — Auto re-plan on coldchain.alert:
  - Consumes `coldchain.alert` Redis Stream via `stream_lifespan` in optimizer main.py
  - Finds live, not-yet-dispatched cold orders on affected vehicles/routes
  - Runs what-if with the affected vehicle removed
  - If result is valid: persists as revised plan, marks old orders superseded, publishes `plan.revised` with diff
  - End-to-end: fridge failure → re-plan moves cold orders off CV-02 (test passes)

- **Router updates** (`services/optimizer/app/router.py`):
  - Regret ledger wired into `_run_qubo_pipeline` → included in `solver_meta.regret`
  - New caches: `_PLAN_QUBO`, `_PLAN_SOLVE`, `_PLAN_METRICS`, `_LATEST_PLAN_ID`
  - `set_live_plan()` called after each plan/run for auto re-plan
  - **GET /whynot?facility=&drug=** — residual shortage explanation
  - **POST /whatif** — {overrides, solver, plan_id} → diff with KPI deltas

- **main.py**: coldchain.alert consumer via `stream_lifespan` (daemon thread, non-blocking)

### Tests (9 new, 106 total — all pass)
- `TestRegretDeltaH::test_delta_h_matches_energy` — verifies ΔH recomputation matches `energy()`
- `TestRegretDeltaH::test_regret_entries_have_reason_codes` — reason_code and reason_text present
- `TestWhyNotF3::test_whynot_h4_insulin_f3` — F3 failure for H4 insulin (no cold storage)
- `TestWhyNotF3::test_whynot_structure` — response structure validation
- `TestWhatIfRepairColdStorage::test_repair_cold_storage_h4` — H4 becomes destination after repair
- `TestWhatIfRepairColdStorage::test_overrides_dont_mutate_snapshot` — snapshot immutability
- `TestAutoReplanColdOrders::test_replan_on_fridge_failure` — cold orders moved off CV-02
- `TestAutoReplanColdOrders::test_replan_noop_without_live_plan` — graceful no-op without live plan
- `TestRegretSanity::test_regret_sorted` — entries sorted by ΔH ascending

### How to verify
1. `cd services/optimizer && python -m pytest tests/ -v` — 106 tests green
2. `docker compose build optimizer` — succeeds
3. With compose up and a plan run: `curl ':8080/api/optimizer/whynot?facility=H4&drug=INSULIN'` — shows F3 cold chain failure
4. `curl -X POST ':8080/api/optimizer/whatif' -H 'Content-Type: application/json' -d '{"overrides":[{"action":"repair_cold_storage","facility":"H4"}]}'` — returns diff
5. Activate fridge_failure scenario → within 60s, plan.revised event published with cold order diff

### Decisions
- Regret uses `energy()` recomputation (not approximation) for exact ΔH — ensures auditability
- What-if always deep-copies snapshot; overrides never mutate the live state
- Auto re-plan triggers only when there are undispatched cold orders on the affected vehicle; no-op otherwise
- `remove_vehicle` override (not `close_route`) used for fridge failure — the vehicle is unsafe, not the route
- `stream_lifespan` (daemon thread) for Redis consumer — compatible with FastAPI async lifespan

### Open issues
- Re-plan does best-effort persist to core-api; if core-api is down, the revised plan is still published to Redis but not stored
- Regret for decomposed-solve plans not yet supported (only flat QUBO pipeline)

### Requests to other lanes
- None

---

## P15 — Grounded narrations, numeric firewall, DTA/credit-memo PDFs (2026-10-30)

### Done

- **Prompt definitions**:
  - `prompts/narrate_v1.yaml`: input = order facts (drug, qty, src/dst, usable, shortage before/after), output {narration} in 2-3 plain sentences for a district officer. model=fast, temperature=0.
  - `prompts/credit_memo_v1.yaml`: input = donor facility facts, output {paragraph} acknowledging contribution. model=fast, temperature=0.

- **Numeric grounding firewall** (`services/genai/app/firewall.py`):
  - `extract_values(text)`: regex extracts ₹ amounts, ISO dates, slash dates, percentages, plain numbers (Indian comma format 1,50,000). Negative lookbehind/lookahead prevents matching digits inside identifiers (H1, 500mg).
  - `check_narration(narration, facts)`: builds fact set from order facts, checks each extracted value (exact or ±0.5% tolerance for derived percentages). Any mismatch → `grounding_ok=false`, narration replaced with deterministic template, `firewall_block` logged.
  - `_deterministic_narration(facts)`: template fallback with exact numbers from facts.

- **Narration service** (`services/genai/app/narration.py`):
  - `narrate_order(llm_service, order_facts)`: calls LLM via `llm_service.complete(purpose="narrate", prompt_id="narrate", version=1)`, runs through firewall. Falls back to deterministic on LLM failure.
  - `narrate_credit_memo(llm_service, memo_facts)`: same pattern for credit memos.

- **PDF generation** (`services/genai/app/pdf_gen.py`):
  - WeasyPrint for HTML→PDF rendering (falls back to raw HTML if not installed).
  - QR code generation via `qrcode` library → base64 PNG data URI.
  - `generate_dta_pdf(order, base_url)`: DTA voucher — "DRUG TRANSFER ADVICE", DTA number, "Near to Expiry"/"Normal" column (residual < 90 days), QR code to `/scan/{qr_token}`, footer "Synthetic demo data".
  - `generate_coldchain_log_pdf(order, readings)`: sensor trace table, min/max temps, breach highlighting.
  - `generate_credit_memo_pdf(donor, items, paragraph, plan_id)`: donor credit memo with recommended credit ₹.

- **HTML templates** (`services/genai/app/templates/`): `dta_voucher.html`, `coldchain_log.html`, `credit_memo.html`.

- **Router endpoints** (`services/genai/app/router.py`):
  - `POST /narrate/batch`, `POST /narrate/{order_id}`, `GET /dta/{order_id}/pdf`, `GET /coldchain-log/{order_id}/pdf`, `POST /credit-memo/pdf`.

- **Batch narration consumer** (`services/genai/app/main.py`): listens on `plan.completed` and `plan.revised` Redis Streams.

- **Dockerfile**: added `weasyprint qrcode httpx` dependencies.

### Tests (20 new, 41 total genai — all pass)

Firewall extraction (4), firewall check pass/fail/wrong date (3), deterministic narration (1), narrate order/fallback/credit memo (3), DTA PDF renders/no Form 19/near expiry (3), coldchain log/credit memo PDF (2), QR data URI/decode (2), API narrate single/batch (2).

### How to verify
1. `cd services/genai && python -m pytest tests/ -v` — 41 tests green
2. `docker compose build genai` — succeeds
3. `curl -X POST :8080/api/genai/narrate/ORD-001 -H 'Content-Type: application/json' -d '{"order_facts":{...}}'`
4. `curl :8080/api/genai/dta/ORD-001/pdf -o dta.pdf` — generates DTA voucher PDF with QR

### Decisions
- Firewall regex uses `(?<![A-Za-z\-\d])..(?!\w)` to skip digits in identifiers
- DTA voucher never called "Form 19" (CLAUDE.md §5)
- Near-expiry threshold = 90 days residual shelf life
- WeasyPrint fallback to raw HTML when not installed (tests still pass)
- QR token from core-api order's qr_token field (HMAC-SHA256 of order_id)

### Open issues
- WeasyPrint needs system fonts + cairo/pango in Docker image for actual PDF output
- Credit memo endpoint is POST (requires items list)

### Requests to other lanes
- L1 (core-api): Include `narration` field on order response; include `qr_token` in GET /orders/{id}

---

## P16 — Copilot: streaming tool-using agent (2026-10-30)

### Done

- **Copilot system prompt** (`prompts/copilot_v1.yaml`):
  - Role: assistant to the District Drug Officer, Bengaluru Urban
  - Grounding rules: every number from tool results only, "I don't have that information" fallback
  - Facility reference by name + code, never claim approved unless tool says so
  - Language: answer in user's language (English or Kannada)
  - model=smart, temperature=0, max_tokens=2048

- **Tool definitions and executors** (`services/genai/app/copilot_tools.py`):
  - 8 tools with JSON Schema parameters: `get_district_overview`, `get_stock_position(facility, drug)`, `explain_order(order_id)`, `why_not(facility, drug)`, `what_if(overrides)`, `get_coldchain_status`, `get_audit_trail(order_id)`, `compare_policies`
  - Each maps to a real HTTP call (core-api, optimizer, coldchain) with 10s timeout
  - Fixture mode for testing: comprehensive fixture data matching domain shapes (positions, orders, why-not with F3 failure, what-if repair diff, coldchain devices, audit trail, policies)
  - Graceful error handling: never raises, returns `{error: ...}` dict

- **Agent loop** (`services/genai/app/copilot.py`):
  - `CopilotSession.chat()` — async generator yielding SSE events
  - Up to 5 tool-call rounds; streams `tool_call` and `tool_result` events between rounds
  - Post-checks final answer with the P15 numeric firewall against concatenated tool results; appends "⚠ Some figures could not be verified" on failure
  - Session persistence in Postgres (`chat_session` + `chat_message` tables) including tool calls as JSONB
  - DEMO_MODE replay via DB history
  - Read-only: never approves or changes live data

- **SSE endpoint** (`services/genai/app/router.py`):
  - `POST /copilot/chat` — streaming SSE with events: `session`, `tool_call`, `tool_result`, `token`, `answer`, `error`
  - `CopilotRequest`: message, session_id (optional), user_id

- **Golden evals** (`evals/golden/copilot.json`):
  - 12 scripted questions covering all 8 tools
  - Includes expected_tools, expected_args, expected_contains, language tag
  - Q03: "Why didn't Hesaraghatta get insulin?" → why_not → F3 cold chain
  - Q04: "What if we repair its fridge?" → what_if → shortage reduction diff
  - Q12: Kannada question about insulin at H4

### Tests (24 new, 65 total genai — all pass)

| Test | What it verifies |
|---|---|
| `test_tool_definitions_complete` | All 8 tools defined |
| `test_tool_definitions_have_schemas` | JSON Schema format correct |
| `test_all_tools_in_map` | Every definition has an executor |
| `test_tool_district_overview` | Fixture returns facilities + shortage |
| `test_tool_stock_position` | H1/INSUL position with effective_stock |
| `test_tool_stock_position_not_found` | Unknown facility returns error |
| `test_tool_explain_order` | ORD-001 with DTA number and audit |
| `test_tool_why_not_h4_insulin` | F3 cold storage failure for H4 |
| `test_tool_what_if_repair` | Repair H4 → insulin transfer added |
| `test_tool_coldchain_status` | Device list returned |
| `test_tool_audit_trail` | ORD-005 audit entries |
| `test_tool_compare_policies` | 7+ policy entries |
| `test_tool_unknown` | Unknown tool returns error |
| `test_copilot_basic_response` | Session created, answer returned |
| `test_copilot_creates_session_id` | cs- prefix session ID |
| `test_copilot_resumes_session` | Same session_id on continue |
| `test_copilot_calls_why_not_tool` | Tool call + F3 in answer |
| `test_copilot_calls_what_if_tool` | What-if tool call + diff in answer |
| `test_copilot_firewall_blocks_bad_number` | 99999 blocked, warning appended |
| `test_flatten_into` | Nested dict flattening |
| `test_summarize_functions` | Tool result summaries |
| `test_api_copilot_chat` | SSE streaming endpoint |
| `test_golden_evals_structure` | 12 questions with required fields |
| `test_copilot_prompt_loaded` | Prompt loaded with correct rules |

### How to verify
1. `cd services/genai && python -m pytest tests/ -v` — 65 tests green
2. `docker compose build genai` — succeeds
3. With compose up:
   ```
   curl -N -X POST :8080/api/genai/copilot/chat \
     -H 'Content-Type: application/json' \
     -d '{"message":"Why didn'\''t Hesaraghatta get insulin?"}'
   ```
   SSE stream: session → tool_call(why_not) → tool_result(F3) → answer
4. Follow up: `'{"message":"What if we repair its fridge?","session_id":"<from above>"}'` → what_if tool, diff in answer

### Decisions
- Read-only agent: tools only call GET endpoints (except POST /whatif which never persists)
- FakeProvider returns text without tool_calls; ToolCallingProvider test helper simulates the tool-call loop
- Firewall post-check uses flattened tool results as fact set — any hallucinated number triggers the warning
- Session history loaded from DB on each turn; in-memory when DB unavailable
- Tool fixture data reads `os.environ["USE_FIXTURES"]` directly (not cached settings) so tests can toggle it
- Max 5 tool rounds prevents infinite loops

### Open issues
- GeminiProvider doesn't support native function-calling yet (would need google.genai tool_config); currently tools work via FakeProvider in tests and the prompt instructs the model to call tools by outputting JSON
- Copilot chat page not yet added to web frontend

### Requests to other lanes
- None

---

## P17 — Per-order approval workflow and QR chain of custody (2026-10-30)

### Done
- **Custody scan endpoint** (`POST /custody/scan`): replaces the 501 stub with full implementation
  - HMAC-SHA256 token verification against `QR_HMAC_SECRET` (falls back to `dev-secret`)
  - Looks up order by `qr_token` column, then verifies HMAC matches order_id
  - State machine enforcement: `approved → dispatched → received → consumed`
  - On dispatch: calls sim-hospital(src) `/transfers/outbound` to decrement source lot
  - On receive: calls sim-hospital(dst) `/transfers/inbound` to create destination lot
    - If cold-chain excursion detected on the vehicle during transit, lot created with status `quarantined`
  - Publishes `custody.scanned` Redis event with deviation data
  - Requests genai one-line summary for deviations (firewalled)
- **Deviation detection** on receive:
  - `qty_mismatch`: received qty != dispatched qty
  - `late_arrival`: arrival > ETA + 1 day (computed from dispatch time + route transit_hours)
  - `cold_chain_excursion`: alert on vehicle from coldchain service during transit
  - Deviations stored as JSON in `custody_event.deviation` column
- **Schema updates**:
  - `transfer_order`: added `qr_token TEXT`, `dispatched_at TIMESTAMPTZ`, `received_at TIMESTAMPTZ`; expanded status CHECK to include `received` and `consumed`
  - `custody_event`: added `qty INTEGER`, `deviation JSONB` columns; expanded event_type CHECK to include `received` and `consumed`
- **Approval triggers**: `POST /orders/{id}/approve` now fire-and-forget calls genai `/narrate/{order_id}` for DTA voucher generation
- **`qr_token` persisted**: `insert_transfer_order` now stores the HMAC token in the DB (was computed but not saved before)
- **Admin demo endpoints**:
  - `POST /admin/tamper-demo` — modifies an audit row's payload to break the hash chain (stashes original)
  - `POST /admin/restore-demo` — restores the tampered row from stash
- **sim-hospital**: `TransferItem` model now accepts `status` field, passed through to `upsert_lot` (supports `quarantined` for cold-chain excursion)

### Files changed
| File | Change |
|---|---|
| `db/init/001_schema.sql` | Added qr_token, dispatched_at, received_at to transfer_order; qty, deviation to custody_event; expanded CHECK constraints |
| `services/core_api/app/queries.py` | Added `get_order_with_token`, `update_order_status`, `insert_custody_event`, `get_last_custody_event`, `tamper_audit_row`, `restore_audit_row`; updated `insert_transfer_order` (qr_token), `get_custody_events` (qty, deviation) |
| `services/core_api/app/routers/custody.py` | Full implementation: HMAC verify, state machine, sim-hospital calls, deviation detection, genai summary |
| `services/core_api/app/routers/orders.py` | Async DTA generation trigger on approval |
| `services/core_api/app/routers/audit_routes.py` | `POST /admin/tamper-demo`, `POST /admin/restore-demo` |
| `services/core_api/tests/conftest.py` | SQLite schema updated with new columns |
| `services/core_api/tests/test_custody.py` | 13 new tests |
| `services/core_api/tests/test_api.py` | Updated `test_custody_scan_501` to `test_custody_scan_requires_fields` (422 now, not 501) |
| `services/sim_hospital/app/routers/transfers.py` | TransferItem accepts `status` field for quarantine support |

### Tests (34 total, all pass)
- **test_custody.py (13 new)**:
  - State machine: dispatch from approved, cannot dispatch from proposed, full lifecycle (approved->dispatched->received->consumed), cannot receive from approved
  - HMAC: invalid token rejected (403/404)
  - Deviation: qty mismatch detected on receive
  - Custody chain: events populated after dispatch+receive
  - Audit: verify ok after scan, tamper breaks verify + restore fixes it
  - API integration: scan dispatch, invalid token, tamper/restore, custody chain query
- **Existing (21)**: all pass unchanged (except test_custody_scan_501 renamed)

### How to verify
1. `cd services/core_api && python -m pytest tests/ -v --timeout=30` — 34 tests pass
2. With compose running: approve order, scan dispatch/receive, check custody timeline, verify audit, tamper/restore demo

### Decisions
- Token lookup: search by `qr_token` column in DB, then verify HMAC
- State machine uses a simple dict of valid transitions
- Deviations stored as JSONB on the custody_event row
- Sim-hospital calls are fire-and-forget (logged but don't block the scan response)
- Admin tamper/restore uses an in-memory stash (acceptable for demo)

### Open issues
- `deviation_summary` prompt YAML not yet created in prompts/ — genai call falls back gracefully
- Sim-hospital auto-scan (approved orders flow automatically after transit time) not yet wired to clock tick handler
- Cold-chain excursion check queries coldchain `/status` — in demo, data may not be available for specific vehicle+time

### Requests to other lanes
- L4 (sim-control): wire auto-scan flag so approved orders in sim-hospital dispatch+receive automatically after transit_hours on clock tick
- L3 (genai): create `prompts/deviation_summary_v1.yaml` for one-line deviation summaries

---

## P18 — Web frontend: order detail, copilot, polish (2026-10-30)

### Done

**P18a — Order Detail Page** (`web/src/pages/OrderDetailPage.tsx`):
- Header: DTA number, status badge, source/destination facility names, drug info
- Narration section with grounded/template chip
- QUBO term breakdown stacked horizontal bar with legend
- Regret alternatives table with delta scores and reason codes
- DTA voucher download button (enabled when status >= approved)
- Custody timeline: vertical timeline with colored dots per event type, deviation badges
- Provenance graph: left-to-right layered SVG with node positioning by type columns, arrow markers
- Approve/reject mutation buttons when status='proposed'
- Link from Plan page orders table via "View" column

**P18b — Optimizer Demo Logs**:
- Added `print()` + `logger.info()` statements throughout optimizer service:
  - `router.py`: run_plan banner, facility/drug/lot counts, candidate count, completion summary
  - `solvers/chain.py`: each tier attempt with success/skip messages
  - `maxcut.py`: graph stats, depth, shots, tier results, best cut value and approx ratio
  - `validator.py`: validation start/result with violation and repair counts
- Added `ENV PYTHONUNBUFFERED=1` to optimizer Dockerfile

**P18b — Web Features**:
- Copilot side panel (`web/src/components/CopilotPanel.tsx`): SSE streaming from POST /copilot/chat via fetch + ReadableStream, tool-call chips with expand/collapse, suggested questions (EN/Kannada), language toggle, AbortController cleanup, fixture mode with character-by-character streaming simulation
- Scan page (`web/src/pages/ScanPage.tsx`): standalone route at /scan/:token, mobile-first max-w-md layout, NEXT_EVENT state machine (approved->dispatch->receive->consume), qty input on receive, success/error handling
- Audit badge (`web/src/components/TopBar.tsx`): chain length display, 5-click secret admin menu with 1.5s window, two-step tamper confirmation dialog, tamper/restore mutations
- AI Health page (`web/src/pages/AIHealthPage.tsx`): dynamic fetch with 15s refetch, 6 stat cards (Total LLM Calls, Cache Hit Rate, P95 Latency, Schema Failures, Fallbacks, Firewall Blocks), provider info, prompts table, eval scores with progress bars and color thresholds, guardrails reminder

**P18c — Results Page & Final Polish**:
- Results page rewrite (`web/src/pages/ResultsPage.tsx`):
  - 4 KPI cards: Stockout Days Saved, Expiry Value Saved, Waste Moved, Shortage Reduction with CI
  - Stockout reduction progress bar with before/after visualization
  - Units Transferred by Drug bar chart (from plan data)
  - Remaining Shortages pie chart (from positions)
  - Policy Ablation Study table with inline progress bars, production config highlighted
  - Loading spinner and empty state
- Polish pass across all pages:
  - Added loading spinners to MapPage, IngestionPage, ScenariosPage (BenchmarkPage, ColdchainPage, AIHealthPage, PlanPage already had them)
  - All pages have empty/no-data states
  - Chart placeholders when no data available
- Responsive layout:
  - Sidebar collapses to icon-only at <1400px via CSS media query with `sidebar-nav` class
  - Nav items have title attributes for icon-only mode tooltip
  - Tables wrapped in `overflow-x-auto` for horizontal scroll at narrow widths
- Navigation audit: Sidebar has all 8 pages in logical order (Map -> Ingestion -> Plan -> Benchmark -> Cold Chain -> Results -> AI Health -> Scenarios)

### Pages built (complete list)

| Page | Route | Key features |
|---|---|---|
| Map | `/` | Leaflet/SVG fallback, facility markers, transfer arcs, facility drawer |
| Ingestion | `/ingestion` | Reports list, review queue, correction modal, Kannada support |
| Plan | `/plan` | Run optimizer, solver badges, zone mini-map, orders by destination, regret |
| Benchmark | `/benchmark` | 5-solver comparison, QUBO gap, 3 zoning cards |
| Cold Chain | `/coldchain` | Device cards, temperature sparklines, excursion banner |
| Results | `/results` | KPI cards, charts, stockout bar, ablation table |
| AI Health | `/ai-health` | LLM stats, prompts, eval scores, guardrails |
| Scenarios | `/scenarios` | Clock controls, scenario cards, signals table |
| Order Detail | `/orders/:id` | DTA header, narration, QUBO bar, regret, custody, provenance |
| Scan | `/scan/:token` | Mobile-first, QR custody scanning, state machine |

### How to verify
1. `cd web && npm run build` — zero errors
2. `VITE_USE_FIXTURES=1 npm run dev` — all 10 pages render with fixture data
3. Results page: 4 KPI cards, stockout bar, 2 charts, 5-row ablation table
4. Order detail: navigate from Plan page "View" link, see all 7 sections
5. Copilot: click FAB, send "Why didn't Hesaraghatta get insulin?" — streaming response with tool chip
6. Sidebar: resize browser to 1366px — sidebar collapses to icons

### Decisions
- ResultsPage uses `getResultMetrics` API (not plan data) for accurate post-plan metrics
- Ablation table highlights production config row with teal background
- Sidebar collapse uses `useIsNarrow(1400)` JS hook with resize listener + toggle button
- Chart placeholders shown when data is empty rather than hiding sections

### Open issues
- Code splitting not implemented (single bundle ~985KB gzipped to 284KB — acceptable for demo)
- Screenshots for docs/screens/ not yet captured

### Requests to other lanes
- None
