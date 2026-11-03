# Judge Audit: MedBalance

**Auditor persona:** Pharmacist + Quantum Computing Researcher + Senior Software Architect
**Date:** 2026-11-03
**Scope:** Full codebase, docs, evidence, UI

---

## Part 1 — Ten Hardest Q&A Questions

### Q1. Your 28-day replay shows greedy-phone-call (Policy B) beats QUBO (Policy D) on stockout reduction by 37 percentage points. Why should anyone use the QUBO solver?

**Honest answer:** The greedy baselines are targeted shortage-first allocators that outperform on the single metric of stockout-days. The QUBO Hamiltonian optimizes a multi-objective function (shortage fill, waste movement, VEN priority, shared-trip cost). Policy D moves 5× more at-risk stock (45,360 vs 8,478 units) and uses fewer trips (245 vs 293). The QUBO's value is in holistic trade-off optimization and as a stepping stone to actual quantum hardware where problem structure matters, not in beating a greedy on one KPI.
**Evidence:** `evidence/eval_reports/replay_20261030_035113.md` — full table with CIs.

### Q2. Every solver evidence JSON shows "No module named 'qpiai_opt'" for tiers 1-3. Has the QpiAI SDK ever actually solved a QUBO in this system?

**Honest answer:** No. The `qpiai-opt` and `qpiai-quantum` packages are declared in `pyproject.toml` and `uv.lock` (real PyPI packages), and the integration code exists, but in every recorded run the modules fail to import and the system falls through to tier 4 (greedy-descent). The QAOA Max-Cut local simulator (`qpiai-quantum`) was tested in unit tests per PROGRESS.md P11, but no evidence JSON shows a successful tier 1 or 2 QUBO solve.
**Evidence:** `evidence/qpiai_runs/20261030T003747_bec2dc5f28cb.json` — all 983 evidence files show tier 4 wins.

### Q3. Your AI evaluation scores are all 100%. Isn't that suspiciously perfect?

**Honest answer:** The "offline" eval runs deterministic parsers (FHIR/CSV) and hand-labelled golden sets (chat/text) through the same extraction and anomaly code. It is testing code against its own golden labels, not testing live LLM extraction. The 100% scores for FHIR/CSV are trivially expected since those are deterministic parsers. The chat/text 100% scores are from the label_helper pre-filling from the current extractor — a circular validation. Live LLM eval depends on GEMINI_API_KEY availability, and the Gemini free tier was exhausted during development.
**Evidence:** `evidence/eval_reports/ai_20261030T041904.json` + `evals/run_evals.py` + `evals/label_helper.py`

### Q4. The DTA voucher says "Drug Transfer Advice" — what regulatory framework does this correspond to? Is this a legally valid transfer document in Karnataka?

**Honest answer:** The DTA is a custom document format for this prototype. It is explicitly NOT called "Form 19" (tested in `test_dta_pdf_never_says_form_19`). Karnataka's actual drug distribution uses Form 19 under the Drugs and Cosmetics Rules. The DTA footer says "Synthetic demo data." No claim of regulatory compliance is made.
**Evidence:** `services/genai/tests/test_narration_firewall_pdf.py:226-230` — Form 19 exclusion test. `docs/PROGRESS.md` P15 decisions.

### Q5. The Copilot streams unverified LLM text to the browser. What stops it from telling a pharmacist to give insulin to a patient with a contraindication?

**Honest answer:** The copilot's numeric firewall catches hallucinated numbers (replaces with deterministic template on mismatch). However, the firewall does NOT check non-numeric clinical claims. The system prompt instructs the LLM to use only tool-result data and say "I don't have that information" otherwise, but prompt-based guardrails are not enforcement. The copilot is a stock-logistics assistant, not a clinical decision tool — it should never give patient-facing advice. This boundary is implicit, not enforced.
**Evidence:** `services/genai/app/firewall.py` — numeric-only checking. `prompts/copilot_v1.yaml` — system prompt.

### Q6. What happens if someone scans a QR code with a forged token? The HMAC secret defaults to "dev-secret."

**Honest answer:** If `QR_HMAC_SECRET` is not set, the system uses `"dev-secret"` as the HMAC key. Anyone who knows an order_id and the default secret can forge a valid QR token and trigger stock movements (dispatch/receive). In the demo environment this is acceptable; in production it would be a critical vulnerability.
**Evidence:** `services/core_api/app/routers/custody.py` line 50.

### Q7. There is no authentication on any endpoint — not even order approval. How do you prevent a malicious actor from approving all orders?

**Honest answer:** Correct — there is zero authentication anywhere in the system. Any HTTP client can approve orders, resolve reviews, reset the simulation, or scan custody events. This is a hackathon prototype running on localhost/private network. Production deployment would require auth (JWT/OAuth) at the gateway level.
**Evidence:** `services/core_api/app/routers/orders.py` — no auth check on approve/reject.

### Q8. LLM-extracted items that pass the anomaly gate go directly to core-api stock upsert without human review. What if the LLM hallucinates a plausible but wrong quantity?

**Honest answer:** The anomaly gate has 6 rules (qty_spike >10×, past_expiry, far_future_expiry, batch_mismatch, unknown_drug, low_confidence <0.85). A plausible hallucination (e.g., 3× the real quantity with a valid drug code and batch) would pass all rules and update stock. The design assumes LLM extraction is a draft that domain experts verify in the review queue — but only flagged items enter the queue. Clean-looking hallucinations would go straight through.
**Evidence:** `services/ingest_ai/app/gate.py` — `_can_upsert` and anomaly checking logic.

### Q9. Your Holt-Winters forecast claims to reduce MAPE from 11.3% to 8.66% with LLM context. But the eval runs offline with golden labels. Has a live LLM ever improved a forecast?

**Honest answer:** The offline eval uses pre-labelled adjusted rates in `evals/golden/forecast.json`. The live path requires an LLM call to produce the context multiplier, but the Gemini free tier was exhausted. The deterministic fallback multiplier (from signal params) is what actually ran in live demos. We cannot prove the LLM adds value beyond the deterministic fallback without live LLM data.
**Evidence:** `evidence/eval_reports/ai_20261030T041904.md` — forecast section. `services/forecast/app/context.py` — fallback path.

### Q10. The benchmark page shows "3.02% gap to MILP." But the replay shows MILP (Policy E) has worse stockout reduction than greedy (Policy C). What does this gap actually measure?

**Honest answer:** The gap measures objective-function value (the QUBO Hamiltonian H), not stockout reduction. The MILP finds the exact minimum of H. H includes waste-movement reward, VEN priority penalties, shared-trip bonus, and shortage-fill — it is NOT a stockout-minimization objective. A small gap to MILP means the QUBO solver is near-optimal for H, but H itself may not correlate with the KPI users care about (stockout-days). This is disclosed in the replay analysis but could be clearer in the UI.
**Evidence:** `evidence/eval_reports/replay_20261030_035113.md` — analysis section. `services/optimizer/app/qubo_builder.py` — Hamiltonian terms.

---

## Part 2 — Unsupported Claims

| # | Claim | Location | Problem | Fix |
|---|-------|----------|---------|-----|
| 1 | Solver tier badge shows "QpiAI Platform" / "QpiAI Local" | `web/src/pages/PlanPage.tsx:15-16` | These tiers have never successfully run (all evidence shows `No module named 'qpiai_opt'`). The badges exist but will always show "Greedy Descent" in practice. | Add a footnote: "Higher tiers available when QpiAI SDK is configured" or grey out unavailable tiers. |
| 2 | "QAOA Max-Cut" zoning card on Benchmark page | `web/src/pages/BenchmarkPage.tsx:134` | QAOA is real code using `qpiai-quantum`, but evidence shows it falls through to brute-force/NetworkX in most runs due to import failures in Docker. | Change card title to "Max-Cut (QAOA chain)" and show actual winning tier, not imply QAOA ran. |
| 3 | AI Health page shows "Total LLM Calls: 142, Cache Hit Rate: 62%" when no calls recorded | `web/src/pages/AIHealthPage.tsx:54` | Banner says "illustrative demo metrics" but stat cards use identical visual treatment as real data. | Add "(demo)" suffix to each card value, or visually dim the cards. |
| 4 | ~~Copilot fixture: "97% of MILP optimality"~~ | `web/src/components/CopilotPanel.tsx` | **FIXED**: Removed "97% of MILP optimality" claim. Compare response now uses replay evidence numbers (QUBO 52%, Greedy F4 86%, Phone-call 89%). All fixture responses prefixed `[Demo response]`. |
| 5 | ~~**Fixture ablation table inverts actual ranking**~~ | `web/src/fixtures/index.ts:333-339` | **FIXED**: Ablation table now uses exact replay evidence numbers. Correct ranking: Phone-call (89.0%) > Greedy F4 (85.9%) > QUBO (52.1%) > MILP (25.8%) > No transfer (0%). | Fixed — numbers from `evidence/eval_reports/replay_20261030_035113.json`. |
| 6 | ~~**Fixture benchmark numbers are fabricated**~~ | `web/src/fixtures/index.ts:166-195` | **FIXED**: Benchmark fixture now sourced from evidence: QUBO energy=21.15, tier=greedy-descent, Max-Cut tier=exact-brute-force/cut=3.40. Shortage_reduction from replay. gap_qubo_to_milp_pct=null (no MILP objective in evidence). Zoning tier corrected from fake "qsv-local" to real "exact-brute-force". |
| 7 | AI eval scores all 100% | `evidence/eval_reports/ai_20261030T041904.md` | Circular validation — `label_helper.py` pre-fills labels from the current extractor, then the eval tests code against its own output. `elapsed_s: 0.0` confirms offline. | Disclose: "Offline eval uses deterministic parsers against auto-generated labels. Live LLM eval pending." |
| 8 | ~~**Fixture AI Health eval scores don't match evidence**~~ | `web/src/fixtures/index.ts`, `AIHealthPage.tsx` | **FIXED**: Eval scores updated to {1.0, 1.0, 1.0} matching `evidence/eval_reports/ai_20261030T041904.json`. Stat cards now show "(demo)" suffix when using demo metrics. Eval scores section shows "offline / deterministic" badge. Demo cards have sky-blue tinted border to visually distinguish from live data. |
| 9 | ~~**CopilotPanel fixture uses non-existent tool names**~~ | `web/src/components/CopilotPanel.tsx` | **FIXED**: Replaced all 4 fake tool names (`check_feasibility`, `get_positions`, `get_coldchain`, `get_benchmark`) with real names from TOOL_MAP (`why_not`, `get_stock_position`, `get_coldchain_status`, `compare_policies`). Args/results match executor shapes. All responses prefixed `[Demo response]`. Fabricated "97%/72%" claims replaced with replay evidence. |
| 10 | "Expiry Avoided" KPI in Results page | `web/src/pages/ResultsPage.tsx` | The replay proves all policies have identical expired INR (2,744). Transfers do not reduce expiry in the model. | Clarify: "Expiry Avoided = at-risk units moved before expiry date, not actual waste prevented." |
| 11 | RTM is empty | `docs/RTM.md` | Contains only a template row. No traceability from requirements to test evidence. | Populate RTM with actual requirement-to-evidence mapping. |
| 12 | Demo script is a placeholder | `docs/DEMO_SCRIPT.md` | Contains only stub headings, no actual demo steps. | Write actual demo walkthrough with expected outputs. |
| 13 | "Violations: 0" badge on Plan page | `web/src/pages/PlanPage.tsx` | The validator repairs violations before reporting. Raw QUBO output averages 1.3 violations per seed (replay). Badge shows post-repair count. | Show "0 (1 repaired)" or similar to be transparent. |
| 14 | **No "simulated data" banner on web UI** | All web pages | DTA PDF has "Synthetic demo data" footer, but web pages show no persistent disclaimer. Live-mode numbers could be mistaken for real district data. | Add "Simulated district data" disclaimer in TopBar or footer. |
| 15 | ~~**Fixture result metrics fabricated**~~ | `web/src/fixtures/index.ts:323-340` | **FIXED**: All metrics now sourced from replay evidence JSON. stockout_days_before=786, after=377, shortage_reduction=0.521, ci from replay CIs. | Fixed — exact numbers from replay_20261030_035113.json. |

---

## Part 3 — Deliverables Checklist

| ID | Deliverable | Status | Evidence / Justification |
|----|-------------|--------|--------------------------|
| D1 | FEFO-based stock position computation | **Demonstrated** | `libs/medbal_common/medbal_common/fefo.py` — 8 unit tests including worked example (50 vials, rate 2/day → 28 effective). Used by core-api positions endpoint. |
| D2 | Multi-format ingestion (FHIR, CSV, Kannada chat, free text) | **Demonstrated** | 4 adapters in `services/ingest_ai/app/adapters.py`, 17 adapter tests, live push/pull endpoints confirmed in CP1/CP2. |
| D3 | LLM extraction with grounding and anomaly detection | **Partially** | Extraction code exists and is tested offline (66 tests). Live LLM extraction failed due to Gemini quota exhaustion — deterministic fallback ran instead. Anomaly gate: 6 rules, 17 tests, review queue works. Grounding: exact + fuzzy matching including Kannada aliases. Live LLM path unproven. |
| D4 | QUBO formulation with brute-force proof | **Demonstrated** | `services/optimizer/app/qubo_builder.py` — 8 brute-force scenario tests all pass. Term breakdown verified. Hamiltonian documented. |
| D5 | 4-tier solver chain (QpiAI cloud → local → SA → greedy) | **Partially** | Chain code exists for all 4 tiers. Only tier 4 (greedy-descent) has ever run successfully. Tiers 1-3 fail with import errors. Evidence: 983 JSON files, all showing tier 4 winner. |
| D6 | MILP exact baseline and benchmark comparison | **Demonstrated** | `services/optimizer/app/milp.py` — OR-Tools CP-SAT, OPTIMAL status on fixture instances. Benchmark endpoint returns 5-solver comparison. Gap calculation verified. |
| D7 | Max-Cut zoning via QAOA | **Partially** | QAOA circuit code exists using `qpiai-quantum`. Local simulator tested in unit tests. In Docker/compose, falls through to brute-force or NetworkX greedy. No evidence of QAOA producing the actual zoning partition in a live run. |
| D8 | Feasibility rules F1-F6 | **Demonstrated** | `services/optimizer/app/feasibility.py` — 18 tests covering all 6 rules including pass/fail for each. F6 blocks controlled drugs (morphine). |
| D9 | Numeric firewall on LLM narrations | **Demonstrated** | `services/genai/app/firewall.py` — regex extraction, fact-checking, deterministic fallback. 7 tests. Any mismatch replaces narration. |
| D10 | Chain of custody with QR/HMAC | **Demonstrated** | `services/core_api/app/routers/custody.py` — HMAC-SHA256 tokens, state machine (proposed→approved→dispatched→received→consumed), deviation detection. 13 tests. Scan page in web UI. |
| D11 | Cold chain monitoring with auto re-plan | **Demonstrated** | Sensor telemetry via MQTT, excursion detection, auto re-plan on `coldchain.alert` Redis event, cold orders moved off affected vehicle. 9 tests for re-plan. Global excursion banner in UI. |
| D12 | Copilot with tool-calling agent | **Partially** | 8 tools defined and tested in fixture mode (24 tests). SSE streaming works. Live LLM tool-calling failed due to Gemini quota. Fallback returns domain lookups labelled as demo. |
| D13 | 28-day replay evaluation | **Demonstrated** | `evidence/eval_reports/replay_20261030_035113.json` — 20 seeds × 28 days × 5 policies + 3 ablations. Reproducible results with CIs. Charts generated. |
| D14 | Forecast with Holt-Winters + LLM context | **Partially** | Holt-Winters baseline works (28 tests). LLM context multiplier path exists but live LLM never ran successfully due to quota. Deterministic fallback from signal params is the actual production path. |
| D15 | Web dashboard (10 pages) | **Demonstrated** | 10 pages confirmed: Map, Ingestion, Plan, Benchmark, Cold Chain, Results, AI Health, Scenarios, Order Detail, Scan. 16 Playwright E2E tests. `npm run build` passes. |
| D16 | ~410 automated tests | **Demonstrated** | Per docs/QA: ~410 tests across unit (299), contract (24), integration (29), E2E (16), eval (10). Multiple test runs documented in execution_report.md. |
| D17 | RTM traceability | **Missing** | `docs/RTM.md` contains only a template row. No requirement-to-evidence mapping exists. |
| D18 | Evidence trail (solver JSON, eval reports) | **Demonstrated** | 983 solver evidence JSONs in `evidence/qpiai_runs/`. 5 replay reports + 3 AI eval reports in `evidence/eval_reports/`. Every solver attempt logged including failures. |

**Summary:** 11 demonstrated, 5 partially demonstrated, 1 missing, 1 N/A.

---

## Part 4 — Safety Holes

### CRITICAL

| # | Vulnerability | Path | Impact | Mitigation |
|---|--------------|------|--------|------------|
| S1 | **No authentication on any endpoint** | All services | Anyone on the network can approve orders, resolve reviews, reset simulation, scan custody, run plans. | Add JWT/OAuth at gateway. Minimum: API key for mutating endpoints. |
| S2 | **HMAC secret defaults to "dev-secret"** | `custody.py:50` | QR tokens forgeable if env var not set. Forged scans can dispatch/receive stock. | Fail startup if `QR_HMAC_SECRET` is unset or equals "dev-secret" in non-demo mode. |
| S3 | **LLM-extracted "clean" items auto-upsert to stock** | `gate.py` → `POST /lots/upsert-batch` | Plausible LLM hallucinations (valid drug, reasonable qty, valid dates) bypass all 6 anomaly rules and update stock without human review. | Add a "pharmacist approval" hold for all LLM-extracted items, or lower the auto-upsert confidence threshold. |
| S4 | **Scan qty has no upper bound** | `custody.py` `req.qty` | User-supplied quantity on custody scan propagates to sim-hospital inbound. Scanner could inject qty=999999. | Validate `scan_qty <= order.qty * 1.1` (allow small variance). |

### MODERATE

| # | Vulnerability | Path | Impact | Mitigation |
|---|--------------|------|--------|------------|
| S5 | **Firewall only checks numeric values** | `firewall.py` | LLM can hallucinate non-numeric claims (wrong facility capabilities, wrong drug properties, clinical advice) that pass the firewall unchecked. | Add entity-checking (facility names, drug codes) against the fact set, not just numbers. |
| S6 | **Copilot fixture responses show specific hardcoded numbers** | `CopilotPanel.tsx` | In fixture mode, numbers like "72% shortage reduction" appear in chat with no "demo" label. Judge could think system computed them. | Prefix fixture responses with "[Demo response]". |
| S7 | **AI Health demo metrics visually identical to real** | `AIHealthPage.tsx` | Banner disclosure exists but stat cards look the same as real data. Quick glance misleads. | Add "(demo)" to card values or grey out the entire card row. |
| S8 | **Order approval actor is self-declared** | `orders.py` | The `actor` field in approve/reject is whatever the caller sends. No identity verification. Audit trail can be spoofed. | Actor should come from authenticated session, not request body. |
| S9 | **Review correction drug_code not re-validated against master** | `review.py` `resolve_review` | Pharmacist correction accepts any drug_code string in `corrected_values`. Could introduce a typo or invalid code into stock. | Validate corrected drug_code against `drugs` table. |

---

## Freeze Issues for PROGRESS.md

The following items should be added to the PROGRESS.md "Open issues" or a new "Freeze issues" section:

### Documentation gaps
1. **RTM empty** — `docs/RTM.md` has only a template row. Must populate before judging.
2. **Demo script placeholder** — `docs/DEMO_SCRIPT.md` has no real content.

### Honesty / disclosure
3. **QpiAI tiers 1-3 never ran** — All 983 evidence files show tier 4 only. Solver badges in UI imply availability.
4. **AI eval circular validation** — `label_helper.py` pre-fills from current extractor; 100% scores are self-referential.
5. **Gemini quota exhausted** — Live LLM paths (extraction, copilot, forecast context, narration) all fell back to deterministic. No live LLM evidence available.
6. **Greedy beats QUBO** — Replay results show simpler policy outperforms on the primary KPI (89% vs 52% stockout reduction). UI should disclose this trade-off.
7. **"Expiry Avoided" metric misleading** — All policies show identical expired INR in replay. Metric measures at-risk units moved, not actual waste prevented.
8. **Violations badge hides repair work** — "Violations: 0" on Plan page is post-repair. Raw QUBO output averages 1.3 violations per run.
9. **Fixture data contradicts replay evidence** — Fixture ablation shows QUBO > Greedy > Phone-call. Replay shows the opposite. Fixture benchmark numbers are fabricated.
10. **Fixture copilot uses non-existent tools** — `check_feasibility` and `get_positions` not in actual tool set.
11. **No "simulated data" banner on web UI** — DTA PDF has disclaimer, web pages do not.

### Security
12. **No auth on any endpoint** — Approve, reject, scan, resolve, reset all unauthenticated.
13. **HMAC dev-secret default** — Custody QR tokens forgeable in default config.
14. **Auto-upsert without human review** — Clean LLM-extracted items go straight to stock DB.
15. **Scan qty unbounded** — User-supplied quantity on custody scan not validated against order qty.
16. **Approval actor self-declared** — Audit trail can be spoofed via request body.
