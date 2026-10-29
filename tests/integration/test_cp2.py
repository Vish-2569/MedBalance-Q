"""
CP2 integration test: scenario-driven checks against the running stack.

Prerequisite: `make down && make build && make seed && make up` (profile full, DEMO_MODE=live).
Run: `python -m pytest tests/integration/test_cp2.py -v --tb=short`

Steps:
  1. Reset sim with seed 42, start clock, wait 2 sim days, pause
  2. dengue_outbreak raises H3 ORS forecast multiplier
  3. bad_data creates review items in ingest-ai
  4. plan uses QUBO tier (any) with 0 violations
  5. benchmark has 5 rows
  6. fridge_failure produces coldchain EXCURSION within 90s
"""
from __future__ import annotations

import time

import pytest
import httpx

GW = "http://localhost:8080"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)
LONG_TIMEOUT = httpx.Timeout(90.0, connect=10.0)


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    c = httpx.Client(base_url=GW, timeout=TIMEOUT)
    yield c
    c.close()


# ── helpers ────────────────────────────────────────────────────────

def wait_for_stack(client: httpx.Client, max_wait: int = 60) -> None:
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            r = client.get("/api/core/health")
            if r.status_code == 200:
                return
        except httpx.ConnectError:
            pass
        time.sleep(2)
    pytest.fail("Stack not reachable within timeout")


def wait_sim_days(client: httpx.Client, target_days: int, max_wait: int = 120) -> None:
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            r = client.get("/api/sim/clock")
            if r.status_code == 200:
                data = r.json()
                if data.get("day_index", 0) >= target_days:
                    return
        except Exception:
            pass
        time.sleep(2)
    pytest.fail(f"Sim did not reach day {target_days} within {max_wait}s")


# ── Step 1: Reset and advance clock ─────────────────────────────

class TestStep1Setup:
    def test_stack_reachable(self, client: httpx.Client) -> None:
        wait_for_stack(client)

    def test_reset_sim(self, client: httpx.Client) -> None:
        r = client.post("/api/sim/reset", params={"seed": 42})
        assert r.status_code == 200, f"Reset failed: {r.status_code} {r.text}"

    def test_advance_clock(self, client: httpx.Client) -> None:
        r = client.post("/api/sim/clock/speed", json={"speed": 10})
        assert r.status_code == 200

        r = client.post("/api/sim/clock/start")
        assert r.status_code == 200

        wait_sim_days(client, target_days=2)

        r = client.post("/api/sim/clock/pause")
        assert r.status_code == 200


# ── Step 2: dengue_outbreak raises H3 ORS forecast ──────────────

class TestStep2Dengue:
    def test_activate_dengue(self, client: httpx.Client) -> None:
        r = client.post("/api/sim/scenario/dengue_outbreak")
        assert r.status_code == 200, f"Activate failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("activated") == "dengue_outbreak"

    def test_forecast_h3_ors_elevated(self, client: httpx.Client) -> None:
        r = client.post(
            "/api/forecast/forecast/run",
            json={"facility_id": "H3", "drug_code": "ORS"},
            timeout=30.0,
        )
        assert r.status_code == 200, f"Forecast run failed: {r.status_code} {r.text}"

        r = client.get("/api/forecast/forecast", params={"facility": "H3", "drug": "ORS"})
        assert r.status_code == 200, f"Forecast GET failed: {r.status_code} {r.text}"
        rows = r.json()
        assert isinstance(rows, list) and len(rows) > 0, f"No forecast rows for H3/ORS"

        row = rows[0]
        multiplier = row.get("context_multiplier") or row.get("multiplier") or 1.0
        assert multiplier > 1.0, (
            f"Expected H3 ORS context_multiplier > 1.0 during dengue outbreak, got {multiplier}"
        )


# ── Step 3: bad_data creates review items ────────────────────────

class TestStep3BadData:
    def test_activate_bad_data(self, client: httpx.Client) -> None:
        r = client.post("/api/sim/scenario/bad_data")
        assert r.status_code == 200

    def test_inject_bad_report(self, client: httpx.Client) -> None:
        """Directly inject a report with obviously bad data to trigger anomaly gate."""
        bad_text = (
            "Stock report PHC Hesaraghatta\n"
            "Paracetamol 500mg batch BN-9999 qty 10000 exp 01/1999\n"
            "Unknown Drug XYZ batch BN-0001 qty 50 exp 06/2027\n"
        )
        r = client.post(
            "/api/ingest/ingest/H4",
            content=bad_text,
            headers={"Content-Type": "text/plain"},
            timeout=30.0,
        )
        assert r.status_code == 200, f"Ingest failed: {r.status_code} {r.text}"
        data = r.json()
        TestStep3BadData._report = data

    def test_reviews_exist(self, client: httpx.Client) -> None:
        """Check review queue for flagged items (from direct inject or sim tick)."""
        r = client.get("/api/ingest/reviews")
        assert r.status_code == 200, f"GET /reviews: {r.status_code} {r.text}"
        reviews = r.json()

        gate = getattr(TestStep3BadData, "_report", {}).get("gate", {})
        flagged_from_inject = gate.get("flagged", 0)

        if isinstance(reviews, list) and len(reviews) > 0:
            pass
        elif flagged_from_inject > 0:
            pass
        else:
            time.sleep(5)
            r = client.get("/api/ingest/reviews")
            assert r.status_code == 200
            reviews = r.json()

        has_reviews = isinstance(reviews, list) and len(reviews) > 0
        has_gate_flags = flagged_from_inject > 0
        assert has_reviews or has_gate_flags, (
            f"Expected review items from bad data. "
            f"Reviews: {len(reviews) if isinstance(reviews, list) else reviews}, "
            f"Gate flagged: {flagged_from_inject}"
        )


# ── Step 4: plan uses QUBO tier with 0 violations ───────────────

class TestStep4Plan:
    _plan_id: str | None = None
    _body: dict = {}

    def test_run_qubo_plan(self, client: httpx.Client) -> None:
        r = client.post(
            "/api/optimizer/plan/run",
            json={"solver": "qubo"},
            timeout=90.0,
        )
        assert r.status_code == 200, f"POST /plan/run: {r.status_code} {r.text}"
        body = r.json()

        plan_obj = body.get("plan", body)
        plan_id = plan_obj.get("id") or plan_obj.get("plan_id") or body.get("plan_id")
        assert plan_id is not None, f"No plan id in response keys: {list(body.keys())}"

        TestStep4Plan._plan_id = plan_id
        TestStep4Plan._body = body

    def test_solver_tier_is_qubo(self, client: httpx.Client) -> None:
        body = TestStep4Plan._body
        plan_obj = body.get("plan", body)
        solver_meta = plan_obj.get("solver_meta", {})
        solver_tier = solver_meta.get("solver_tier") or plan_obj.get("solver_tier", "")

        qubo_tiers = {
            "qpiai-platform", "qpiai-local", "neal-sa", "greedy-descent",
            "decomposed-qpiai-platform", "decomposed-qpiai-local",
            "decomposed-neal-sa", "decomposed-greedy-descent",
        }
        is_qubo_tier = any(t in solver_tier for t in qubo_tiers)
        assert is_qubo_tier, (
            f"Expected a QUBO tier, got solver_tier='{solver_tier}'. "
            f"solver_meta keys: {list(solver_meta.keys())}"
        )

    def test_zero_violations(self, client: httpx.Client) -> None:
        body = TestStep4Plan._body
        plan_obj = body.get("plan", body)
        solver_meta = plan_obj.get("solver_meta", {})
        violations = solver_meta.get("violations", plan_obj.get("violations"))

        assert violations is not None, f"No violations field. solver_meta: {solver_meta}"
        assert violations == 0, f"Expected 0 violations, got {violations}"


# ── Step 5: benchmark has 5 rows ────────────────────────────────

class TestStep5Benchmark:
    def test_benchmark_5_rows(self, client: httpx.Client) -> None:
        plan_id = TestStep4Plan._plan_id
        assert plan_id, "No plan_id from step 4"

        r = client.get(
            f"/api/optimizer/plan/{plan_id}/benchmark",
            timeout=90.0,
        )
        assert r.status_code == 200, f"GET /benchmark: {r.status_code} {r.text}"
        data = r.json()

        benchmark = data.get("benchmark") or data.get("rows") or data
        if isinstance(benchmark, dict) and "rows" in benchmark:
            benchmark = benchmark["rows"]

        assert isinstance(benchmark, list), f"Expected list, got {type(benchmark)}"
        assert len(benchmark) == 5, (
            f"Expected 5 benchmark rows, got {len(benchmark)}. "
            f"Solvers: {[r.get('solver') for r in benchmark]}"
        )


# ── Step 6: fridge_failure → coldchain EXCURSION within 90s ─────

class TestStep6Fridge:
    def test_activate_fridge_failure(self, client: httpx.Client) -> None:
        r = client.post("/api/sim/scenario/fridge_failure")
        assert r.status_code == 200, f"Activate failed: {r.status_code} {r.text}"

    def test_coldchain_excursion_within_90s(self, client: httpx.Client) -> None:
        """Poll coldchain status until at least one device shows EXCURSION."""
        r = client.post("/api/sim/clock/start")
        assert r.status_code == 200

        deadline = time.time() + 90
        found = False
        last_states = []

        while time.time() < deadline:
            try:
                r = client.get("/api/coldchain/status")
                if r.status_code == 200:
                    devices = r.json()
                    if isinstance(devices, list):
                        last_states = [
                            (d.get("device_id"), d.get("state"))
                            for d in devices
                        ]
                        for d in devices:
                            state = d.get("state", "").upper()
                            alert = d.get("alert", False)
                            if state == "EXCURSION" or alert:
                                found = True
                                break
                if found:
                    break
            except Exception:
                pass
            time.sleep(5)

        client.post("/api/sim/clock/pause")

        assert found, (
            f"No coldchain EXCURSION detected within 90s. "
            f"Last device states: {last_states}"
        )
