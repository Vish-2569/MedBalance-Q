# MedBalance-Q Test Cases

## E2E Demo Path (Playwright)

| ID | Requirement | Steps | Expected | Actual | Status |
|---|---|---|---|---|---|
| E2E-01 | Map shows facilities | Navigate to /; check for ≥4 Leaflet/SVG markers | Map renders with 4+ facility markers | 5 markers rendered (W0, H1-H4) | PASS |
| E2E-02 | Kannada ingestion | Navigate to /ingestion; expand H3 report | Kannada text (ಇನ್ಸುಲಿನ್) visible; insulin extracted | Kannada raw text shown; INSUL item present | PASS |
| E2E-03 | Bad data flagged | Check ingestion page for H4 flagged report | qty_spike anomaly; review queue with explanation | qty_spike badge; "data entry error" explanation | PASS |
| E2E-04 | Review resolved | Click Accept on pending review item | Review action fires; UI updates | Accept button clicked; status changed | PASS |
| E2E-05 | Scenario activation | Navigate to /scenarios | Simulation Clock heading; dengue_outbreak card visible | Both visible | PASS |
| E2E-06 | Plan with solver tier | Navigate to /plan | Solver tier badge; Violations: 0; ORD- entries | QpiAI Local badge; 0 violations; 6 orders | PASS |
| E2E-07 | Insulin order usable=28 | Open ORD-005 detail | DTA number, Insulin, qty 28, Cold Chain badge | All shown correctly | PASS |
| E2E-08 | Benchmark 5 rows | Navigate to /benchmark | 5 solver names; gap 3.02% | All 5 solvers; 3.02% gap badge | PASS |
| E2E-09 | Cold chain excursion | Navigate to /coldchain | Excursion Detected banner; 3 sensors listed | Banner + sensor-01/02/03 visible | PASS |
| E2E-10 | Copilot why-not | Open copilot; ask about Hesaraghatta insulin | Response contains F3 or cold storage | "F3" and "cold storage" in fixture response | PASS |
| E2E-11 | Approve order | Open ORD-001; click Approve | Approve button present and clickable | Button clicked successfully | PASS |
| E2E-12 | Voucher download | Check order detail for download button | Download icon button visible | Button present | PASS |
| E2E-13 | Scan dispatch/receive | Navigate to /scan/ORD-004; dispatch then receive | Status transitions: approved→dispatched→received | Both transitions completed | PASS |
| E2E-14 | Audit verified | Check TopBar on map page | Audit chain count (47) visible | "47" shown in TopBar | PASS |
| E2E-15 | Results dashboard | Navigate to /results | KPI cards; 72% shortage reduction; ablation table | All present including Full QUBO row | PASS |
| E2E-16 | AI Health | Navigate to /ai-health | Gemini provider; 72% cache hit rate | Both displayed | PASS |

## Unit Test Coverage (pytest)

| ID | Area | Tests | Requirement | Status |
|---|---|---|---|---|
| UT-01 | FEFO math | 8 | Correct effective_stock, at_risk, reserve, shortage | PASS |
| UT-02 | Audit chain | 6 | Hash chain integrity, tamper detection | PASS |
| UT-03 | Settings | 3 | Placeholder detection, key_status | PASS |
| UT-04 | Feasibility F1-F6 | 19 | All 6 rules: identity, route, cold chain, usable, reserve, controlled | PASS |
| UT-05 | Candidates | 13 | Chunk split 50/25/25%, usable formula, top-3 selection | PASS |
| UT-06 | Baselines | 7 | Greedy phone-call, greedy F4, reserve protection | PASS |
| UT-07 | QUBO builder | 10 | Hamiltonian terms, brute-force proof for 8 scenarios | PASS |
| UT-08 | QUBO properties | 7 | Hypothesis: upper-triangular, finite energy, cap 150 vars | PASS |
| UT-09 | Solver chain | 14 | 4-tier fallthrough, validator, repair, evidence JSON | PASS |
| UT-10 | Max-Cut + MILP | 19 | QAOA circuit, CP-SAT, scale mode 40 facilities, zoning | PASS |
| UT-11 | Regret/WhyNot/WhatIf | 10 | ΔH accuracy, F3 explanation, snapshot immutability | PASS |
| UT-12 | Replay eval | 10 | Conservation, determinism, policy ordering, violations | PASS |
| UT-13 | Adapters | 20 | FHIR, CSV, Chat, Text parsing | PASS |
| UT-14 | Grounding | 13 | Exact, fuzzy, Kannada, unknown | PASS |
| UT-15 | Extraction | 22 | Scan text, validate, date resolution, pipeline | PASS |
| UT-16 | Anomaly rules | 18 | 6 rules: qty_spike, past_expiry, far_future, batch_mismatch, unknown_drug, low_confidence | PASS |
| UT-17 | Gate + Review | 10 | Clean forwarding, flagged review, resolve actions | PASS |
| UT-18 | Forecast | 22 | Holt-Winters, EWMA, guardrails, signals, store, API | PASS |
| UT-19 | GenAI gateway | 22 | Prompt registry, validation, cache, LLM service, retry | PASS |
| UT-20 | Narration + PDF | 19 | Firewall extraction, grounding check, DTA voucher, QR | PASS |
| UT-21 | Copilot | 25 | 8 tools, agent loop, firewall, golden evals | PASS |
| UT-22 | Sim control | 12 | Clock, scenarios, signals, reset | PASS |
| UT-23 | Sim hospital | 22 | FEFO dispensing, Poisson, transfers, reporters | PASS |
| UT-24 | Sensors | 13 | Device telemetry, fault mode, no-Redis resilience | PASS |
| UT-25 | Coldchain | 18 | State machine, alerts, store, downsampling | PASS |
| UT-26 | Core API | 35 | Endpoints, upsert, custody, audit | PASS |

## Contract Tests

| ID | Requirement | Tests | Status |
|---|---|---|---|
| CT-01 | Fixture JSON matches OpenAPI schema | 16 parametrized | PASS |
| CT-02 | OpenAPI YAML valid | 1 | PASS |
| CT-03 | Fixture JSON valid | 1 | PASS |
| CT-04 | Plan structure (6 orders, insulin usable=28) | 1 | PASS |
| CT-05 | Cross-fixture consistency | 3 | PASS |
| CT-06 | Events.md completeness | 1 | PASS |

## Integration Tests

| ID | Requirement | Tests | Status |
|---|---|---|---|
| INT-CP1 | Walking skeleton: reset, clock, lots, plan, orders, audit | 15 | PASS |
| INT-CP2 | Scenarios: dengue, bad data, QUBO plan, benchmark, fridge | 14 | PASS |

## AI Evaluation Gates

| ID | Gate | Threshold | Score | Status |
|---|---|---|---|---|
| AI-01 | Extraction drug-code exact match | ≥ 85% | 100.0% | PASS |
| AI-02 | Extraction qty accuracy | ≥ 90% | 100.0% | PASS |
| AI-03 | Extraction expiry accuracy | ≥ 80% | 100.0% | PASS |
| AI-04 | Extraction batch accuracy | ≥ 75% | 100.0% | PASS |
| AI-05 | Anomaly recall | ≥ 90% | 100.0% | PASS |
| AI-06 | Anomaly FPR | ≤ 10% | 0.0% | PASS |
| AI-07 | Narration firewall pass rate | ≥ 90% | 100.0% | PASS |
| AI-08 | Forecast adjusted MAPE better than baseline | Yes | 8.66% < 11.30% | PASS |
| AI-09 | Copilot tool-choice accuracy | ≥ 80% | 100.0% | PASS |
| AI-10 | Copilot numeric/keyword match | ≥ 70% | 100.0% | PASS |
