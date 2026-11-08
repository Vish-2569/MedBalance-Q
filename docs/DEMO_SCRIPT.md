# MedBalance-Q Demo Script

> District-level redistribution of near-expiry essential medicines using quantum-inspired optimization.
>
> **Simulated district data — not connected to live systems.**

---

## Prerequisites

| Item | Detail |
|------|--------|
| Environment | Docker Compose (16 containers) or fixture mode (`USE_FIXTURES=1`) |
| Browser | Chrome/Edge, 1400px+ width recommended |
| Keys in `.env` | `GEMINI_API_KEY` (for live LLM), `JWT_SECRET` (any 32+ char string), `QR_HMAC_SECRET` |
| Start command | `.\tasks.ps1 up` (Docker) or `cd web && npm run dev` (fixture mode) |
| URL | `http://localhost:8080` (Docker) or `http://localhost:5173` (Vite dev) |

For a quick demo without Docker, set `VITE_USE_FIXTURES=1` in `web/.env` and run `npm run dev`. All screens work with fixture data; LLM calls return pre-scripted responses prefixed `[Demo response]`.

---

## Step 0 — Login (1 min)

1. Open the app. The **Login Page** appears with the MedBalance-Q branding.
2. Four demo accounts are shown as quick-login buttons:
   - **Dr. Ramesh Kumar** — `district_officer` (approves/rejects orders)
   - **Smt. Kavitha N.** — `pharmacist` (scans custody, resolves reviews)
   - **System Admin** — `admin` (all actions, tamper demo)
   - **Sim Operator** — `operator` (clock control, scenarios)
3. Click **Dr. Ramesh Kumar** (district officer) to log in.
4. The **TopBar** shows: sim clock, play/pause controls, speed selector, live event feed, audit badge ("Ledger verified"), and user badge with name/role and sign-out button.
5. **Talk track:** "All state-changing endpoints require JWT authentication. Four roles map to real district health workflows. The system won't let a pharmacist approve orders, or an operator tamper with the audit chain."

> **Fixture mode:** Login is bypassed automatically; all features work without a backend.

---

## Step 1 — District Overview / Map (2 min)

1. The **Dashboard** page loads by default, showing:
   - An interactive Leaflet map of Bengaluru Urban district
   - **5 facilities**: W0 (warehouse) + H1–H4 (hospitals/PHCs)
   - Circle markers colored by stock health (green = healthy, amber = shortage, red = stockout)
   - Polylines showing planned transfers (blue dashed = cold chain, teal = ambient)
   - Facility count and planned transfer count in the header
   - A collapsible **How to Use** guide panel explains the map markers, transfer arcs, and facility health colors.
2. Click a facility marker to open the **Facility Drawer** with lot-level inventory and position details.
3. **Talk track:** "W0 is the district warehouse. H1–H4 are hospitals with varying stock levels. H4 is a rural PHC with no cold storage — this drives a key feasibility constraint we'll see later. The arcs show the optimizer's proposed redistribution plan."

---

## Step 2 — Ingestion & Review (3 min)

1. Navigate to **Ingestion** in the sidebar. A collapsible guide panel explains the four report formats, the AI extraction pipeline, and the anomaly gate workflow.
2. Point out the stat cards: Reports Received, Flagged, Pending Reviews, Resolved.
3. Point out the amber banner: "2 items need pharmacist review".
4. Show the **4 report cards** with different formats:
   - **H1** — FHIR R5 (structured, deterministic extraction)
   - **H2** — e-Aushadhi CSV (structured, deterministic)
   - **H3** — Chat (Kannada) — click to expand: raw Kannada text on the left, GenAI-extracted items on the right with confidence scores
   - **H4** — Free Text (flagged) — bad data: qty=10,000 insulin, expiry=1999
5. Scroll to the **Review Queue** table:
   - `qty_spike` anomaly for H4's insulin (10,000 vials vs ~50 typical) — pending review
   - `low_confidence` for H3's paracetamol (Kannada fuzzy match) — already accepted
   - `unknown_drug` for H3's paracetamol (matched via Kannada alias) — pending
6. Click the **Accept** button (checkmark) on a pending review item to resolve it.
7. **Talk track:** "Four hospitals report in four different formats. The GenAI extraction pipeline handles FHIR, CSV, free text, and Kannada chat messages. An anomaly gate flags suspicious data — like 10,000 vials from a PHC that usually stocks 50. A pharmacist reviews flagged items before they enter inventory. The LLM never decides feasibility — it extracts, and deterministic rules validate."

---

## Step 3 — Scenario Console (2 min)

1. Navigate to **Scenarios**. A collapsible **How Scenarios Work** guide panel with a 5-step Quick Start explains the simulation engine, scenario types, and signal interpretation. Each scenario card shows its impact and affected pages. Signals are displayed with human-readable descriptions instead of raw JSON.
2. Show the **Simulation Clock** panel: current date, day index, speed, play/pause/reset controls.
3. Show **Active Scenarios**: `baseline` is active (normal consumption).
4. Show **Available Scenarios**: `dengue_outbreak`, `fridge_failure`, `bad_data`, `road_closure`, `td_campaign`.
5. Point out the **Recent Signals** table showing fired signals.
6. (Optional) Click **Activate** on `dengue_outbreak` — this triggers a 3x ORS demand spike at H3.
7. **Talk track:** "The simulation engine drives consumption with Poisson-distributed daily demand. Scenarios inject real-world disruptions — disease outbreaks, equipment failures, bad data. Each scenario fires signals that the forecast service can pick up to adjust demand multipliers."

---

## Step 4 — Redistribution Plan (3 min)

1. Navigate to **Plan**. A collapsible guide panel explains key concepts: QUBO Hamiltonian, DTA vouchers, feasibility rules F1–F6, solver tiers, zone partitioning, and gap to MILP.
2. Show the header: "Redistribution Plan" with the **solver tier badge** (e.g., "QpiAI Local" or "Greedy Descent").
3. Point out the **Pipeline Stages** showing the optimization pipeline: positions → feasibility → candidates → QUBO → solve → validate.
4. Show **KPI cards**: shortage reduction, transfers, cost, expiry avoided.
5. Show the **Violations badge**: "Violations: 0 (2 repaired)" — the validator caught and trimmed infeasible allocations.
6. Show the **Orders table** with 6 transfer orders, each with DTA number, source → destination, drug, quantity, score, status.
7. Point out **ORD-005** (insulin, cold chain) — routed from W0 to H2 (which has cold storage), NOT to H3 (which doesn't).
8. Click **Run Optimizer** to show the live pipeline (or explain it runs in the background with SSE progress events in the top bar).
9. **Talk track:** "The QUBO Hamiltonian balances shortage reduction, trip cost, overfill penalty, and batch consolidation. Feasibility rules F1–F6 gate every candidate: drug identity, route existence, cold chain requirements, usable shelf life, reserve protection, and controlled substance blocking. The solver tries QpiAI Platform → QpiAI Local → dwave-neal SA → greedy descent, recording which tier succeeded."

---

## Step 5 — Order Detail & Approval (2 min)

1. Click any order (e.g., **ORD-001**) in the plan table.
2. Show the **Order Detail** page:
   - DTA number (format: `DTA/BLR-U/2026/000001`)
   - Drug info, quantity, source → destination, temperature requirement
   - **Narration**: LLM-generated 2–3 sentence explanation grounded in exact numbers
   - **QUBO score breakdown**: shortage reward, trip cost, overfill penalty, batch bonus
   - **Regret analysis**: top alternative not chosen and why
3. Click **Approve** (requires `district_officer` or `admin` role).
4. The status changes to "approved" and a DTA voucher PDF generation is triggered.
5. Click the **Download** button to get the DTA voucher PDF.
6. **Talk track:** "Every order has an LLM narration that passes a numeric grounding firewall — if any number doesn't match the facts, the narration falls back to a deterministic template. The regret analysis shows what the optimizer considered and rejected, making decisions auditable."

---

## Step 6 — Benchmark Comparison (2 min)

1. Navigate to **Benchmark**. A guide panel explains what each benchmark metric means and how to interpret the solver comparison.
2. Show the page with:
   - **Gap badge**: QUBO Gap to MILP Optimum percentage
   - **Solver Objective chart** (bar chart comparing 5 solvers)
   - **Shortage Reduction chart** (bar chart)
   - **Benchmark table** with all 5 policies: no-transfer, greedy-phone-call, greedy-f4, QUBO (greedy-descent), MILP (OPTIMAL)
   - **Zoning Comparison**: QAOA Max-Cut vs k-means vs exact brute-force
3. **Talk track:** "We don't claim quantum advantage. We benchmark against exact MILP and greedy baselines. The QUBO moves 5x more at-risk stock as a multi-objective trade-off — it optimizes a Hamiltonian that balances shortage, waste, and cost simultaneously. The zoning comparison shows QAOA Max-Cut achieves the exact brute-force partition on this 5-node graph."

---

## Step 7 — Cold Chain Monitoring (2 min)

1. Navigate to **Cold Chain**. A guide panel explains cold chain monitoring concepts, excursion detection, and what the state badges mean.
2. Show the **Excursion Detected** banner (red) if sensor-03 is in excursion.
3. Show stat cards: Total Devices, Active Alerts, Avg Temperature.
4. Show **device cards** with sensor IDs, temperature readings, and state (ok/warning/excursion).
5. Point out sensor-03 on V2: 9.8°C, trending up from 4.5°C — temperature history visualized.
6. **Talk track:** "MQTT sensors stream temperature data. The state machine tracks ok → warning → excursion transitions. When a cold-chain order arrives via an excursion vehicle, the custody scan automatically flags a cold_chain_excursion deviation and quarantines the lot."

---

## Step 8 — Copilot (2 min)

1. Click the **Copilot** button (bottom-right floating button).
2. Show suggested questions in English. Toggle to **Kannada** using the language button.
3. Click **"Why didn't Hesaraghatta get insulin?"**
4. Watch the response stream in with tool calls:
   - `why_not` tool: shows H3 failed F3 (no cold storage)
   - Explanation: H3 doesn't have cold storage, F3 requires cold route + cold vehicle + destination cold storage
5. Try **"Compare policies"** to see the benchmark comparison in natural language.
6. Show **LLM attribution** below assistant messages: model name and prompt ID.
7. **Talk track:** "The copilot uses retrieval-augmented tool calling — it can query stock positions, explain why a facility didn't receive a drug, and compare policies. All responses show source attribution. The copilot works in English and Kannada."

---

## Step 9 — Custody Scan (2 min)

1. From an approved order, note the **QR token** or navigate directly to `/scan/<order-id>`.
2. The **Scan Page** shows:
   - QR icon, DTA number, status badge
   - Drug info, quantity, source → destination
   - **Dispatch** button (for approved orders)
3. Click **Dispatch**. Status changes to "dispatched", success flash appears.
4. The page now shows **Receive** with a quantity input (leave blank for full quantity, or enter a different number to trigger qty_mismatch deviation).
5. **Talk track:** "In the field, a pharmacist scans the QR code on the DTA voucher. The token is an HMAC-signed hash of the order ID. The scan endpoint verifies the token, validates the state transition (approved → dispatched → received → consumed), and detects deviations: quantity mismatch, late arrival, or cold chain excursion. Each deviation gets an LLM-generated summary."

---

## Step 10 — Audit & Tamper Detection (2 min)

1. Point out the **Audit badge** in the top bar: "Ledger verified" with a checkmark and entry count.
2. (Admin only) Click the audit badge **5 times quickly** to open the admin panel.
3. Click **Tamper audit row** → **Confirm**.
4. The badge turns red and pulses: "Tampered at #N".
5. Click **Restore audit row** to fix the chain.
6. Badge returns to green: "Ledger verified".
7. **Talk track:** "Every state change — order approval, custody scan, review resolution — appends to a hash-chained audit log. Each entry's hash includes the previous entry's hash, creating a tamper-evident chain. If any row is modified, the chain breaks and the UI immediately shows where. This is the same principle as blockchain integrity, without a blockchain."

---

## Step 11 — Results Dashboard (1 min)

1. Navigate to **Results**. A guide panel explains the evaluation methodology, KPI definitions, ablation study approach, and what the confidence intervals mean.
2. Show KPI cards: Stockout Days Before/After, Shortage Reduction with 95% CI bounds, Transfer Orders, Units Proposed.
3. Show the **Ablation table** with 5 variants (A–E) comparing no-transfer, phone-call greedy, greedy-f4, QUBO, MILP.
4. Point out the **[Illustrative]** badge — eval scores are from offline deterministic evaluation, not live runs.
5. **Talk track:** "The 20-seed × 28-day replay evaluation shows QUBO achieves 52.1% shortage reduction (CI: 51.3%–52.8%). Greedy baselines achieve higher stockout reduction (89%) but the QUBO moves 5x more at-risk stock. We report honest numbers, including where simpler baselines outperform."

---

## Step 12 — AI Health (1 min)

1. Navigate to **AI Health**. A guide panel explains the GenAI gateway architecture, call statistics, prompt catalog, eval scores, and the narration firewall.
2. Show: provider (Gemini), model names (fast/smart), total calls, cache hit rate, P95 latency, schema failures, fallbacks, firewall blocks.
3. Show **prompt table** with call counts per prompt ID.
4. Show **eval score bars** for extraction, anomaly explanation, narration.
5. Point out the **golden rule reminder**: "LLMs read and explain; deterministic code decides."
6. **Talk track:** "Every LLM call goes through a single gateway with structured output validation, retry logic, and fallback tiers. The cache deduplicates identical prompts. The firewall blocks any narration where numbers don't match the grounding facts."

---

## Key Technical Points for Judges

| Criterion | Evidence |
|-----------|----------|
| QpiAI usage | Solver tries QpiAI Platform → Local → neal SA → greedy. Evidence JSON in `evidence/qpiai_runs/`. QAOA Max-Cut for zoning. |
| GenAI integration | 8 prompts via Gemini, structured output, grounding firewall, demo/record/replay modes |
| Quantum-inspired optimization | QUBO Hamiltonian with 5 terms, ≤150 variables, benchmarked against MILP optimum |
| Real-world constraints | F1–F6 feasibility, FEFO, cold chain, VEN priority, reserve protection |
| Evaluation | 20-seed × 28-day replay, 5-policy ablation, CI bounds, honest reporting |
| Security | JWT auth (4 roles), HMAC QR tokens, hash-chained audit, input validation |
| Auditability | DTA vouchers, custody chain, provenance graph, regret analysis, LLM attribution |

---

## Teardown

```powershell
.\tasks.ps1 down
```
