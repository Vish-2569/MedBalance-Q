# Architecture Decisions

## ADR-001: Folder names use underscores, Docker names use hyphens
**Status:** Accepted
**Context:** Python imports need underscores; Docker conventions use hyphens.
**Decision:** services/core_api/ in the filesystem, core-api in docker-compose.
**Consequences:** Need to remember the mapping when writing Dockerfiles.

## ADR-002: py-base build-only image
**Status:** Accepted
**Context:** Every service needs medbal_common installed.
**Decision:** A shared base image built first; all services FROM it.
**Consequences:** Build target runs `docker compose build py-base` first.

## ADR-003: Money as INR number with 2 decimal places
**Status:** Accepted
**Context:** Need a money representation for transfer costs in the API. Options: integer paise or floating-point INR.
**Decision:** Use `number` type with 2 decimal places, field suffix `_inr` (e.g. `cost_inr: 1250.00`). Not integer paise because the UI shows INR directly and there's no currency conversion or precise arithmetic requirement — this is a cost estimate, not a financial ledger.
**Consequences:** All API schemas and fixtures use this convention. If precision ever becomes critical, migrate to integer paise.

## ADR-004: sim-hospital single image with HOSPITAL_ID
**Status:** Accepted
**Context:** 4 hospital instances needed.
**Decision:** One image, 4 compose services with different HOSPITAL_ID env and port mappings.

## ADR-005: structlog only (no python-json-logger)
**Status:** Accepted
**Context:** Need JSON logging. Two libraries available.
**Decision:** structlog only — simpler, one dependency.

## ADR-006: Audit DDL for both SQLite and Postgres
**Status:** Accepted
**Context:** Tests use SQLite in-memory; prod uses Postgres.
**Decision:** audit.py exports both CREATE_AUDIT_TABLE (SQLite) and CREATE_AUDIT_TABLE_PG.

## ADR-007: Fixture serving with USE_FIXTURES=1
**Status:** Accepted
**Context:** All 4 lanes need working endpoints before any business logic is built.
**Decision:** `medbal_common.fixtures.serve(app, service_name)` registers routes returning fixture JSON when USE_FIXTURES=1. Fixtures live in contracts/fixtures/ and are COPY'd into Docker images.
**Consequences:** Every service can serve realistic data day 1. Fixture routes are replaced by real implementations incrementally.

## ADR-008: Deterministic seed generator with pure-Python Poisson
**Status:** Accepted
**Context:** Need 90 days of consumption history with realistic variance. numpy would be a heavy dependency just for random numbers.
**Decision:** Use inverse-CDF Poisson sampling with `random.Random(seed)` for full determinism without numpy. Generator reads from YAML configs, outputs SQL and per-hospital JSON.
**Consequences:** `make seed` is reproducible across all 4 laptops. Different seeds produce different but structurally identical data.
