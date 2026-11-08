# MedBalance-Q — Project Overview

MedBalance-Q is a district-level medicine redistribution system that prevents drug wastage and stockouts by intelligently transferring near-expiry medicines from facilities with surplus to those facing shortages. The system covers a simulated Bengaluru Urban district with one warehouse (W0) and four hospitals (H1--H4), managing lot-level inventory across multiple drug types with cold chain constraints.

This document explains every section of the frontend application as seen in the navigation bar and supporting UI elements.

---

## Top Bar

The top bar is a persistent header displayed on every page. It contains:

- **Brand Mark & Title** — "MedBalance-Q" branding with the project logo.
- **Simulation Clock** — Shows the current simulated date (e.g. `2026-11-03`), day index, and whether the clock is LIVE or PAUSED. The simulation does not use real wall-clock time; it runs on an accelerated virtual clock so that days of district operations can be replayed in seconds.
- **Play/Pause & Speed Controls** — Operators can start, pause, and change the simulation speed (1x, 2x, 5x, 10x) directly from the top bar without navigating to the Scenarios page.
- **Live Event Feed** — A scrolling ticker showing the 3 most recent system events in real time via Server-Sent Events (SSE). Events include `report.received`, `plan.completed`, `order.status`, `custody.scanned`, `coldchain.alert`, `forecast.updated`, and `anomaly.flagged`. Each event is color-coded: teal for plan events, red for alerts/anomalies, grey for routine updates.
- **Audit Ledger Badge** — Displays the integrity status of the tamper-evident audit chain. Shows "Ledger verified" (green) when the hash chain is intact, or "Tampered at #N" (red, pulsing) if a break in the chain is detected. The system verifies the audit log every 10 seconds. A hidden admin menu (activated by 5 rapid clicks) allows demo tampering and restoration to showcase the tamper-detection feature.
- **User Badge & Sign Out** — Shows the logged-in user's name and role (e.g. `ddo / admin`), with a sign-out button.

---

## Excursion Banner

Not a navigation item, but a critical alert bar that appears between the top bar and the main content area whenever a **cold chain excursion** is detected. It displays in red with a warning icon: "COLD CHAIN EXCURSION — N active alert(s). Affected lots may be quarantined." This banner is driven by real-time SSE events of type `coldchain.alert` with severity `excursion`, ensuring operators are immediately notified regardless of which page they are on.

---

## 1. Dashboard (Map View)

**Route:** `/` | **Icon:** Map | **Label:** Dashboard

The landing page provides a geographic overview of the entire district.

### What it shows:
- **Interactive Map** — A Leaflet map centered on Bengaluru (12.965, 77.605) displaying all facilities as colored circle markers. Warehouses are shown with larger markers than hospitals. If map tiles fail to load (offline mode), it falls back to a custom SVG district diagram.
- **Facility Health Colors** — Each facility marker is colored based on its current stock health: green (healthy), amber (some shortages), red (critical shortages/stockouts). The color is computed from the facility's inventory positions.
- **Transfer Arcs** — Lines drawn between source and destination facilities for all planned transfer orders. Solid teal lines represent ambient transfers; dashed blue lines represent cold chain transfers.
- **Facility Drawer** — Clicking any facility marker opens a side drawer showing that facility's detailed stock positions, lot-level inventory, shortages, at-risk quantities, and reserves.
- **Summary Stats** — Header shows the total number of facilities and planned transfers.
- **Sim Date Context** — The current simulation date is passed to the facility drawer for contextual display.

### Purpose:
Gives the District Drug Officer an at-a-glance view of where shortages and surpluses exist across the district and how the redistribution plan connects them.

---

## 2. Ingestion & Review

**Route:** `/ingestion` | **Icon:** FileInput | **Label:** Ingestion | **Badge:** Pending review count

This page handles the intake of hospital stock reports and the human-in-the-loop review process for AI-extracted data.

### What it shows:

#### Report Intake
- **Pull Hospital Reports** — Fetches live stock reports from the 4 simulated hospitals (H1--H4). Each hospital may report in a different format: FHIR R5, e-Aushadhi CSV, free-text, or chat messages in Kannada.
- **Load Demo Samples** — Seeds the system with synthetic demo reports covering all formats and languages. Auto-triggers on first visit if no reports exist.
- **Report Cards** — Each report is displayed as an expandable card showing:
  - Facility code, input channel (FHIR, CSV, Chat, Free Text), language (English, Kannada, Mixed)
  - Extraction method badge: "GenAI extracted" (purple) when the LLM successfully parsed it, or "Offline extraction" (amber) when the deterministic fallback was used
  - Status: processed, flagged, or pending
  - "Synthetic demo" badge for generated test data
  - Expandable detail showing the raw text side-by-side with extracted items (drug code, quantity, batch number, expiry, confidence score)

#### Review Queue
- **Stat Cards** — Reports Received, Flagged, Pending Reviews, Resolved.
- **Review Table** — Lists all items that were flagged by the anomaly detection gate. Each row shows facility, drug, extracted quantity, confidence score (color-coded: green >= 85%, amber >= 60%, red < 60%), anomaly type (e.g. `qty_spike`, `unknown_drug`), anomaly explanation, and current status.
- **Review Actions** — For pending items, a pharmacist can:
  - **Accept** — Confirm the AI extraction is correct as-is
  - **Correct** — Open a modal to fix the drug code (from a verified catalog dropdown), quantity, and expiry date
  - **Reject** — Discard the extracted item entirely

### Purpose:
Ensures that AI-extracted inventory data is validated by a human pharmacist before it enters the system. The LLM extracts structured data from messy, multi-format, multi-language hospital reports, but deterministic code and human review make the final decisions (the "golden rule").

---

## 3. Redistribution Plan

**Route:** `/plan` | **Icon:** ClipboardList | **Label:** Plan

The core operational page where the QUBO-based optimizer generates and displays the medicine redistribution plan.

### What it shows:

#### Run Controls
- **Run Optimizer** — Triggers the full optimization pipeline: snapshot current inventory, run feasibility checks (F1--F6), zone facilities via Max-Cut, build the QUBO matrix, solve it, validate results, and persist transfer orders.

#### Solver Information
- **Solver Tier Badge** — Shows which solver tier was used: QpiAI Platform (purple), QpiAI Local (blue), Simulated Annealing/neal (amber), or Greedy Descent (grey). The system tries each tier in order and falls back if one is unavailable.
- **Gap to MILP** — Displays the optimality gap between the QUBO solution and the exact MILP (Mixed-Integer Linear Programming) optimum. The project explicitly does not claim quantum advantage.
- **Violations Count** — Number of constraint violations remaining after validation (ideally 0), plus how many were repaired.

#### Solver Attempts
- Shows each solver tier that was tried, whether it succeeded or was skipped, and how long it took.

#### KPI Cards
- **Transfers** — Total number of transfer orders generated
- **Shortage Reduction** — Percentage of district-wide shortage eliminated by the plan
- **At-risk Units Redistributed** — Count of near-expiry units moved before they would have expired
- **Cost** — Total estimated transport cost in INR

#### Pipeline Stages
- Visual pipeline showing the 7 stages: Snapshot -> Feasibility -> Zoning -> QUBO Build -> Solve -> Validate -> Persist

#### Zone Partition (Max-Cut)
- Mini-map SVG showing how facilities were partitioned into zones using QAOA Max-Cut. Each zone is color-coded (blue, amber, purple). Shows the tier used (QpiAI QCloud, local simulator, exact brute-force, or NetworkX) and the cut value.

#### Solver Benchmark (inline)
- Compact comparison table of all solver strategies: shortage reduction, waste moved, trips, and solve time.

#### Transfer Orders by Destination
- Orders grouped by destination facility, each group expandable. Each order shows:
  - DTA number (Drug Transfer Advice voucher ID, format: `DTA/BLR-U/2026/NNNNNN`)
  - Drug name, source facility, quantity, score
  - Cold chain indicator (snowflake icon) for temperature-sensitive drugs
  - Status (proposed/approved/dispatched/received/consumed)
  - Link to the order detail page

#### Regret Analysis
- Lists alternatives the optimizer considered but did not select, with the delta score and reason. This transparency shows the operator what trade-offs were made.

### Purpose:
The heart of the system. Transforms inventory data into actionable, auditable transfer orders that a District Drug Officer can review, approve, and execute.

---

## 4. Benchmark

**Route:** `/benchmark` | **Icon:** BarChart3 | **Label:** Benchmark

A dedicated analytics page comparing different solver strategies side by side.

### What it shows:

#### Gap Badge
- QUBO Gap to MILP Optimum percentage and Max-Cut Zoning tier with approximation ratio.

#### Multi-Objective Disclaimer
- Prominent info box explaining that greedy baselines optimize a single objective (shortage filling) while QUBO and MILP optimize five objectives simultaneously (shortage, expiry avoidance, cost, overfill, batch consolidation). Higher shortage reduction does not mean a better plan.

#### Charts
- **Solver Objective Comparison** — Bar chart comparing the combined objective score across all solvers: no-transfer baseline, greedy-phone-call, greedy-f4, QUBO (qpiai-local), MILP (OPTIMAL). Each solver is color-coded.
- **Shortage Reduction by Solver** — Bar chart showing shortage reduction percentages.

#### Detailed Table
- Full comparison table with columns: Solver, Objective, Shortage Reduction, Expiry Avoided, Waste Moved, Trips, Time (ms). MILP and QUBO rows are highlighted.

#### Zoning Comparison
- Side-by-side cards comparing three zoning approaches:
  - **QAOA Max-Cut** — The primary zoning method using QpiAI QCloud
  - **k-means** — Geographic clustering baseline
  - **Exact Brute-Force** — Exhaustive search (feasible for small facility counts)
- Each card shows the zone assignments, cut value, intra-zone cost, and approximation ratio.

### Purpose:
Provides evidence-based comparison showing how the QUBO approach performs relative to classical baselines and the theoretical optimum. Critical for the project's honest assessment that it does not claim quantum advantage.

---

## 5. Cold Chain

**Route:** `/coldchain` | **Icon:** Thermometer | **Label:** Cold Chain | **Badge:** Active alert count

Real-time monitoring of cold chain equipment (sensors on vehicles and facility refrigerators).

### What it shows:

#### Excursion Banner
- Page-level red banner if any device is in excursion state, listing affected device IDs.

#### Stat Cards
- Total devices, OK count, Excursion count.

#### Device Cards
- One card per cold chain device, color-coded by state:
  - **OK** (teal) — Temperature within the 2--8 degree C range
  - **Warning** (amber) — Approaching limits
  - **Excursion** (red) — Temperature outside the safe range; lots in transit may need quarantine
- Each card contains:
  - **Temperature Sparkline** — A line chart showing recent temperature history with the 2--8 degree C safe zone shaded in blue. The line color changes based on state (teal/amber/red).
  - **Current Temperature** — Precise reading in degrees C, color-coded
  - **Battery Level** — With red highlight when below 20%
  - **Last Seen** — Timestamp of the most recent MQTT message
  - **Device ID, Vehicle/Facility Assignment**
- Data auto-refreshes every 5 seconds.

### Purpose:
Enforces feasibility rule F3 (cold chain). The system blocks transfers of cold-chain drugs (like insulin) through vehicles with excursions or to facilities without cold storage. This page lets operators monitor the physical cold chain in real time.

---

## 6. Results

**Route:** `/results` | **Icon:** Trophy | **Label:** Results

Post-optimization dashboard summarizing what the redistribution plan achieved.

### What it shows:

#### Live Plan Results
- **Metric Cards** — Transfer Orders count, Units Proposed, Shortage Reduction percentage, At-risk Units Redistributed (with cost).
- **Units Proposed by Drug** — Bar chart showing how many units of each drug were proposed for transfer.
- **Current Shortages by Facility and Drug** — Pie chart showing remaining shortages after the plan.

#### Policy Ablation (Offline Replay Evaluation)
- Results from a 20-seed x 28-day replay evaluation comparing different policies:
  - **No transfer** — Baseline with zero redistribution
  - **Greedy Phone-Call** — Manual ad-hoc approach
  - **Greedy F4** — Algorithmic greedy with feasibility checks
  - **QUBO** — The system's QUBO-based optimizer
  - **MILP** — Exact optimal solution
- Bar chart with 95% confidence interval error bars for QUBO.
- Detailed ablation table showing shortage reduction, at-risk units moved, cost, and explanatory notes for each variant.
- Labelled as "[Illustrative]" to indicate these are from offline simulation, not live results.

### Purpose:
Shows the measurable impact of the redistribution plan and provides statistical evidence of policy effectiveness across multiple simulation runs.

---

## 7. AI Health

**Route:** `/ai-health` | **Icon:** Brain | **Label:** AI Health

Operational dashboard for monitoring the GenAI gateway and all LLM-powered features.

### What it shows:

#### Gateway Info
- Provider name (Gemini), Fast Model ID, Smart Model ID.

#### Performance Metrics
- **Total LLM Calls** — Count of all LLM invocations in the last 24 hours
- **Cache Hit Rate** — Percentage of calls served from the demo-mode cache (key = hash of prompt + model + input)
- **P95 Latency** — 95th percentile response time in milliseconds (red if > 2000ms)
- **Schema Failures** — Count of times the LLM's structured output failed Pydantic validation
- **Fallbacks** — Count of calls that fell back to deterministic templates after LLM failure
- **Firewall Blocks** — Count of narrations blocked by the grounding firewall (LLM-generated text that contained numbers not present in the source data)

#### Prompt Catalog
- Table listing all registered prompt templates with their ID, version, and call count.

#### Eval Scores
- Progress bars showing evaluation scores for different GenAI capabilities (e.g. extraction accuracy, narration quality). Color-coded: green >= 90%, amber >= 70%, red < 70%.

#### Guardrails Reminder
- "LLMs read and explain; deterministic code decides." — Reinforcing the golden rule with the validation pipeline: Structured output -> Pydantic validation -> 2 retries -> template fallback.

### Purpose:
Ensures transparency and operational oversight of all AI components. Every LLM call is tracked, cached, validated, and auditable. This page makes it visible when the AI is struggling (high fallback rate, low cache hits, schema failures) so operators can trust the system.

---

## 8. Scenarios

**Route:** `/scenarios` | **Icon:** Beaker | **Label:** Scenarios

Control panel for injecting simulation events and stress-testing the system.

### What it shows:

#### Simulation Clock Controls
- Full clock management: current date, day index, running/paused state, speed selector, play/pause buttons.
- **Reset** — Resets the entire simulation to a given random seed, clearing all active scenarios, resetting all 4 simulated hospitals, and starting fresh.

#### Scenario Cards
- **Active Scenarios** — Currently running scenarios shown with a green indicator.
- **Available Scenarios** — Inactive scenarios that can be activated with a single click:

| Scenario | Effect |
|---|---|
| **baseline** | Normal operations, no disruptions |
| **dengue_outbreak** | 3x demand for ORS and Paracetamol at H3 (days 5--15), simulating an IDSP outbreak alert |
| **fridge_failure** | Cold van CV-02 compressor failure, temperature rises to 18.5 degrees C, triggering cold chain excursion |
| **bad_data** | H4 sends a garbled stock report with OCR errors, testing the ingest-ai anomaly detection |
| **ilr_repaired** | Ice-Lined Refrigerator at H4 restored, re-enabling cold chain routes through that facility |
| **road_closure** | Roads between H3 and H1 closed, blocking those transfer routes (tests feasibility rule F2) |
| **td_campaign** | Tetanus-diphtheria immunization campaign at H1, 2x TD demand (days 3--10) |

#### Signals Table
- Lists all fired signals with ID, type (outbreak, device_fault, data_quality, equipment_repair, route_closure, campaign), parameters, and timestamp.

### Purpose:
Allows demo operators to inject realistic disruptions and observe how the entire system responds end-to-end: from data ingestion to forecast adjustment to optimizer re-planning to cold chain alerting.

---

## Order Detail Page

**Route:** `/orders/:id` | **Not in sidebar** — accessed by clicking "View" on any transfer order

Deep-dive into a single transfer order with full traceability.

### What it shows:
- **Header** — DTA number, status badge, cold chain indicator, source -> destination facilities, drug name, quantity, batch number, creation date, optimization score.
- **Approve/Reject** — Action buttons for orders in "proposed" status. Rejection requires a reason (max 500 characters).
- **AI Narration** — LLM-generated human-readable explanation of why this transfer was proposed. Shows whether the narration passed the grounding firewall ("grounded") or fell back to a template.
- **QUBO Term Breakdown** — Stacked horizontal bar showing the four QUBO terms that make up the order's score: Shortage Reward (teal), Batch Bonus (blue), Trip Cost (red, negative), Overfill Penalty (amber, negative).
- **Regret Alternatives** — Table of alternative facilities the optimizer considered, with regret scores and reasons they were not selected.
- **DTA Voucher Download** — Button to download the Drug Transfer Advice PDF voucher (available only after approval).
- **Custody Timeline** — Vertical timeline of all custody events: dispatch, receive, consume. Each event shows the actor, quantity, location, temperature, and any deviations.
- **Provenance Graph** — Left-to-right SVG flowchart tracing the order's lineage: Report -> Extraction -> Lot -> Candidate -> Order -> Custody -> Audit. Each node is color-coded by type and shows metadata (confidence, score, quantity, status, actor).

### Purpose:
Provides complete audit trail and explainability for every transfer order — from the original hospital report through AI extraction, optimization scoring, human approval, physical custody, to final consumption.

---

## QR Scan Page

**Route:** `/scan` and `/scan/:token` | **Not in sidebar** — standalone mobile-friendly page

A mobile-optimized interface for scanning QR codes on DTA vouchers during physical medicine transfers.

### What it shows:
- **Order Summary Card** — DTA number, drug name, quantity, batch, source -> destination, cold chain indicator, score.
- **Status-Aware Actions**:
  - **Approved** -> "Dispatch" button (blue) — Records the physical handoff from source facility
  - **Dispatched** -> "Receive" button (teal) — Records arrival at destination, with optional quantity input for partial receipts
  - **Received** -> "Consume" button (green) — Records that the medicine has been administered/consumed
- **Success Flash** — Green confirmation banner after each scan action.
- **Terminal State** — Shows "Order consumed/rejected/cancelled — Custody chain complete" when no further actions are possible.

### Purpose:
Bridges the digital system to physical logistics. Field workers scan a QR code on the printed DTA voucher to advance the order through its lifecycle, creating an auditable custody chain without needing the full desktop interface.

---

## Copilot Panel

**Not in sidebar** — accessible via a floating action button (bottom-right corner)

An AI-powered conversational assistant for the District Drug Officer.

### What it shows:
- **Slide-out Panel** — Opens from the right side of the screen (420px wide).
- **Language Toggle** — Switch between English and Kannada (the local language of Karnataka state).
- **Suggested Questions** — Pre-built prompts like "Why didn't Hesaraghatta get insulin?", "Show cold-chain status", "Compare policies", "Show district overview" (with Kannada equivalents).
- **Streaming Responses** — Real-time SSE streaming of copilot answers with a thinking indicator.
- **Markdown Rendering** — Responses include formatted tables, bold text, code snippets, and numbered/bulleted lists.
- **Tool Call Chips** — Expandable chips showing which backend tools the copilot invoked (e.g. `why_not`, `get_stock_position`, `compare_policies`, `what_if`, `get_coldchain_status`, `explain_order`, `get_audit_trail`, `get_district_overview`) along with the arguments and results. This provides transparency into how the AI arrived at its answer.
- **Model & Prompt Info** — Small metadata line showing which LLM model and prompt template were used for each response.
- **Retry & Clear** — Retry failed responses, clear entire conversation.

### Capabilities:
- Stock position queries across facilities and drugs
- Why-not analysis explaining why a transfer was or wasn't made
- Order explanation and audit trail retrieval
- Cold chain status summaries
- What-if scenario analysis (e.g. "What if H4 cold storage is repaired?")
- Policy comparison across solver strategies
- Kannada language support for all queries

### Purpose:
Gives the District Drug Officer a natural-language interface to interrogate the system, understand optimizer decisions, and explore what-if scenarios without needing to navigate through multiple pages.

---

## Sim Data Banner

A thin footer bar displayed at the bottom of every page:

> "Simulated district data -- not connected to live systems"

Ensures that users always know they are looking at synthetic demonstration data, not real patient or inventory information. All facility names are prefixed with `SIM-` for the same reason.
