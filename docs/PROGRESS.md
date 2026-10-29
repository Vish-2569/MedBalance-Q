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
