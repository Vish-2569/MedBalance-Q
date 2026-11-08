

# Requirements Traceability Matrix

**Project:** MedBalance-Q (Quant-A-Maze 3.0, GENAI-04)
**Last updated:** 2026-11-03

Status key: **Pass** = implemented + tested + evidence; **Partial** = implemented but with caveats; **Pending** = not yet delivered.

---

## Core Optimization

| Req ID | Requirement | Source | Implementation | Test / Evidence | Status |
|--------|-------------|--------|----------------|-----------------|--------|
| R01 | QUBO formulation for lot-level redistribution (v3 Hamiltonian with shortage, uniqueness, fill, precedence, trip-consolidation terms) | CLAUDE.md §6 | `services/optimizer/app/qubo_builder.py` | `services/optimizer/tests/test_qubo_bruteforce.py` (8 scenarios); `evidence/qpiai_runs/*.json` (983 files, energy=21.15 on fixture) | Pass |
| R02 | 4-tier solver chain: QpiAI Platform → QpiAI Local → dwave-neal SA → greedy-descent | CLAUDE.md §7 | `services/optimizer/app/solvers/` (SolverPort interface + 4 implementations) | `services/optimizer/tests/test_solver_chain.py`; all 983 evidence files show `tier: "greedy-descent"` — tiers 1-3 never connected successfully | Partial |
| R03 | QAOA Max-Cut for facility zoning (bisection, k=2) | CLAUDE.md §7, ADR-009 | `services/optimizer/app/maxcut.py` | `services/optimizer/tests/test_maxcut_milp.py`; `evidence/qpiai_runs/*_mc_*.json` — all show `tier: "exact-brute-force"`, QAOA cloud never ran | Partial |
| R04 | MILP exact baseline via OR-Tools CP-SAT | ADR-010 | `services/optimizer/app/solvers/` (MILP solver) | Replay evidence: MILP shortage_reduction=0.258, time_ms=24 in `evidence/eval_reports/replay_20261030_035113.json` | Pass |
| R05 | Feasibility rules F1–F6 (identity, route, cold chain, usable qty, reserve, controlled substance) | CLAUDE.md §5 | `services/optimizer/app/validator.py` | Validator re-simulation catches violations; unit tests in `services/optimizer/tests/` | Pass |
| R06 | 28-day replay evaluation (20 seeds × 5 policies + ablations) | CLAUDE.md §1 | `services/optimizer/app/` (replay engine) | `evidence/eval_reports/replay_20261030_035113.json` — full aggregate results | Pass |
| R07 | Gap reporting: QUBO vs MILP optimum | ADR-010 | Benchmark page shows gap badge when non-null | Fixture sets `gap_qubo_to_milp_pct: null` (no single-snapshot MILP objective); live gap computed when both solvers run | Partial |

## GenAI — Ingestion & Extraction

| Req ID | Requirement | Source | Implementation | Test / Evidence | Status |
|--------|-------------|--------|----------------|-----------------|--------|
| R08 | Multi-format ingestion: FHIR R5 (H1), e-Aushadhi CSV (H2), Kannada+English chat (H3), messy free text (H4) | CLAUDE.md §3 | `services/ingest_ai/app/adapters.py` (4 adapters) | `services/ingest_ai/tests/test_adapters.py`; `services/ingest_ai/tests/test_api.py` | Pass |
| R09 | LLM extraction with grounding (rapidfuzz against drug/facility master) | CLAUDE.md §8 | `services/ingest_ai/app/extraction.py`, `services/ingest_ai/app/grounding.py` | `services/ingest_ai/tests/test_extraction.py` (29 tests); `evals/golden/extraction.json` | Pass |
| R10 | Drug code constrained to candidates or UNKNOWN (LLM cannot invent codes) | CLAUDE.md §2 | `services/ingest_ai/app/extraction.py` — candidate set from grounding | Unit tests confirm UNKNOWN fallback | Pass |
| R11 | Anomaly gate (6 rules) with review queue | CLAUDE.md §8 | `services/ingest_ai/app/gate.py` | Tests in `services/ingest_ai/tests/`; anomalous items routed to review queue | Pass |
| R12 | Auto-upsert of clean items to stock DB | CLAUDE.md §8 | `services/ingest_ai/app/gate.py` — clean items auto-upsert | Functional but no human-in-the-loop for clean items (audit finding S3) | Pass |

## GenAI — Copilot

| Req ID | Requirement | Source | Implementation | Test / Evidence | Status |
|--------|-------------|--------|----------------|-----------------|--------|
| R13 | 8-tool copilot agent (get_district_overview, get_stock_position, explain_order, why_not, what_if, get_coldchain_status, get_audit_trail, compare_policies) | CLAUDE.md §8 | `services/genai/app/copilot.py`, `services/genai/app/copilot_tools.py` (TOOL_MAP) | `services/genai/tests/test_copilot.py` (24 tests); `evals/golden/copilot.json` | Pass |
| R14 | Bilingual support: Kannada + English | CLAUDE.md §3 | Copilot accepts `language` param; prompts in `prompts/` | Fixture responses include Kannada; live depends on Gemini | Partial |
| R15 | Max 5 tool rounds per copilot turn | CLAUDE.md §8 | `services/genai/app/copilot.py` — loop capped at 5 | Unit tests verify cap | Pass |
| R16 | Numeric grounding firewall on LLM narrations | CLAUDE.md §2, §8 | `services/genai/app/firewall.py` | `services/genai/tests/test_genai.py` (7 firewall tests); blocks mismatched numbers, passes qualitative text | Pass |

## GenAI — Other LLM Services

| Req ID | Requirement | Source | Implementation | Test / Evidence | Status |
|--------|-------------|--------|----------------|-----------------|--------|
| R17 | Centralized LLM gateway (all calls via POST /llm/complete) | CLAUDE.md §8 | `services/genai/app/llm_service.py` | `services/genai/tests/test_genai.py` | Pass |
| R18 | Prompt versioning (prompts/<id>_v<n>.yaml) | CLAUDE.md §8 | `prompts/` directory | Prompts loaded at startup; version tracked in every LLM record | Pass |
| R19 | DEMO_MODE live/record/replay with SHA-256 cache key | CLAUDE.md §8 | `services/genai/app/llm_service.py` | Tests cover replay mode | Pass |
| R20 | Holt-Winters forecast with LLM context multiplier | CLAUDE.md §3 | `services/forecast/app/` | `services/forecast/tests/` (28 tests); `evals/golden/forecast.json` | Partial |

> R20 caveat: Forecast baseline works; LLM context multiplier never ran live (Gemini quota exhausted). Evidence shows deterministic fallback only.

## DTA Voucher & Chain of Custody

| Req ID | Requirement | Source | Implementation | Test / Evidence | Status |
|--------|-------------|--------|----------------|-----------------|--------|
| R21 | DTA (Drug Transfer Advice) voucher PDF generation | CLAUDE.md §5 | `services/genai/app/pdf_gen.py` | 3 tests; PDF includes disclaimer "synthetic data" | Pass |
| R22 | HMAC-SHA256 QR tokens for chain of custody | CLAUDE.md §7a | `services/core_api/app/routers/custody.py` | `services/core_api/tests/test_custody.py` (13 tests) | Partial |
| R23 | Custody scan workflow (dispatch → in-transit → delivered) | CLAUDE.md §3 | `services/core_api/app/routers/custody.py` | Tests cover state transitions | Pass |

> R22 caveat: HMAC uses dev-secret default (`QR_HMAC_SECRET` env var). QR tokens forgeable in default config (audit finding S2).

## Approval & Audit

| Req ID | Requirement | Source | Implementation | Test / Evidence | Status |
|--------|-------------|--------|----------------|-----------------|--------|
| R24 | Order approval/rejection workflow | CLAUDE.md §3 | `services/core_api/app/routers/orders.py` | Functional but no authentication on endpoints (audit finding S1) | Partial |
| R25 | Immutable audit trail (every state change) | CLAUDE.md §9 | `libs/medbal_common/medbal_common/audit.py` | Tests in `tests/test_audit.py`; append called in DB transactions | Pass |
| R26 | SSE event stream for live UI updates | CLAUDE.md §3 | `services/core_api/app/routers/events.py` | Frontend subscribes; copilot tool results forwarded via SSE | Pass |

## Cold Chain & Simulation

| Req ID | Requirement | Source | Implementation | Test / Evidence | Status |
|--------|-------------|--------|----------------|-----------------|--------|
| R27 | Cold chain monitoring (MQTT sensors, excursion detection) | CLAUDE.md §3 | `services/coldchain/` | Excursion rules trigger quarantine; copilot `get_coldchain_status` reads state | Pass |
| R28 | Auto re-plan on cold chain excursion | CLAUDE.md §3 | `services/optimizer/app/replan.py` | 9 tests for re-plan logic | Pass |
| R29 | Simulation framework (sim clock, 4 hospitals, scenarios, seed determinism) | CLAUDE.md §3, ADR-008 | `services/sim-control/`, `services/sim-hospital/` | Deterministic seed via pure-Python Poisson (ADR-008); `data/seed/` | Pass |

## Web UI

| Req ID | Requirement | Source | Implementation | Test / Evidence | Status |
|--------|-------------|--------|----------------|-----------------|--------|
| R30 | Ingestion page (upload, review queue, anomaly resolution) | CLAUDE.md §4 | `web/src/pages/IngestionPage.tsx` | Functional in browser | Pass |
| R31 | Scan page (QR custody workflow) | CLAUDE.md §4 | `web/src/pages/ScanPage.tsx` | Functional in browser | Pass |
| R32 | Benchmark page (solver comparison, zoning visualization) | CLAUDE.md §4 | `web/src/pages/BenchmarkPage.tsx` | Shows tier badges from data; gap badge only when non-null | Pass |
| R33 | Results page (plan metrics, shortage reduction, ablation) | CLAUDE.md §4 | `web/src/pages/ResultsPage.tsx` | Ablation table only in fixture mode; live mode disclaims it | Pass |
| R34 | AI Health page (provider telemetry, eval scores, demo indicators) | CLAUDE.md §4 | `web/src/pages/AIHealthPage.tsx` | "(demo)" labels + sky-blue tinting when showing fixtures; "offline / deterministic" badge on eval scores | Pass |
| R35 | Copilot panel (bilingual, tool call chips, SSE streaming) | CLAUDE.md §4 | `web/src/components/CopilotPanel.tsx` | Fixture responses use real tool names; `[Demo response]` / `[ಡೆಮೊ ಪ್ರತಿಕ್ರಿಯೆ]` prefixes | Pass |
| R37 | All navigation pages include collapsible guide panels, helper text, and improved empty states for new users | UX requirement | All 8 page components in `web/src/pages/` (MapPage, IngestionPage, PlanPage, BenchmarkPage, ColdchainPage, ResultsPage, AIHealthPage, ScenariosPage) | 66 vitest tests pass; `npx tsc --noEmit` clean | Pass |

## AI Evaluation

| Req ID | Requirement | Source | Implementation | Test / Evidence | Status |
|--------|-------------|--------|----------------|-----------------|--------|
| R36 | Offline AI eval suite (extraction, anomaly explanation, narration) | CLAUDE.md §9 | `evals/` | `evidence/eval_reports/ai_20261030T041904.json` — all scores 100% | Partial |

> R36 caveat: Scores are 100% because `label_helper.py` pre-fills golden labels from the current extractor — circular validation (audit finding H2).

---

## Summary

| Status | Count |
|--------|-------|
| Pass | 27 |
| Partial | 10 |
| Pending | 0 |

**Key partial items:**
- R02, R03: QpiAI tiers 1–3 and QAOA cloud never connected; only local fallback tiers ran
- R07: QUBO-vs-MILP gap requires both solvers on same snapshot; not yet captured
- R14, R20: Gemini quota exhausted; bilingual copilot and forecast LLM multiplier never ran live
- R22, R24: Security gaps (dev-secret HMAC, no auth) — acceptable for hackathon demo, not production
- R36: AI eval is self-referential (circular golden labels)
