"""
CP1 integration test: walking-skeleton end-to-end against the running stack.

Prerequisite: `make down && make build && make seed && make up` (profile full, DEMO_MODE=live).
Run: `python -m pytest tests/integration/test_cp1.py -v --tb=short`

Steps:
  1. Reset sim with seed 42
  2. Start clock, wait for 2 sim days
  3. Assert lots exist for H1..H4 (via core-api)
  4. Run a plan (via optimizer)
  5. Assert >=1 order, all orders usable>0, no controlled drug, audit verify ok
"""
from __future__ import annotations

import time

import pytest
import httpx

GW = "http://localhost:8080"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

CONTROLLED_DRUGS: set[str] = {"MORPHINE"}


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    c = httpx.Client(base_url=GW, timeout=TIMEOUT)
    yield c
    c.close()


# ── helpers ────────────────────────────────────────────────────────

def wait_for_stack(client: httpx.Client, max_wait: int = 60) -> None:
    """Block until gateway and core-api are reachable."""
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
    """Poll sim clock until day_index >= target_days."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            r = client.get("/api/sim/clock")
            if r.status_code == 200:
                data = r.json()
                day = data.get("day_index", 0)
                if day >= target_days:
                    return
        except Exception:
            pass
        time.sleep(2)
    pytest.fail(f"Sim did not reach day {target_days} within {max_wait}s")


# ── Step 1: Reset sim ─────────────────────────────────────────────

class TestStep1Reset:
    def test_stack_reachable(self, client: httpx.Client) -> None:
        wait_for_stack(client)

    def test_reset_sim(self, client: httpx.Client) -> None:
        r = client.post("/api/sim/reset", params={"seed": 42})
        assert r.status_code == 200, f"Reset failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("seed") == 42 or data.get("seed") == "42"


# ── Step 2: Start clock, wait 2 sim days ──────────────────────────

class TestStep2Clock:
    def test_start_clock(self, client: httpx.Client) -> None:
        r = client.post("/api/sim/clock/speed", json={"speed": 10})
        assert r.status_code == 200, f"Set speed failed: {r.status_code} {r.text}"

        r = client.post("/api/sim/clock/start")
        assert r.status_code == 200, f"Start failed: {r.status_code} {r.text}"

    def test_wait_2_days(self, client: httpx.Client) -> None:
        wait_sim_days(client, target_days=2)

    def test_pause_clock(self, client: httpx.Client) -> None:
        r = client.post("/api/sim/clock/pause")
        assert r.status_code == 200, f"Pause failed: {r.status_code} {r.text}"


# ── Step 3: Assert lots exist for H1..H4 ──────────────────────────

class TestStep3Lots:
    @pytest.mark.parametrize("facility", ["H1", "H2", "H3", "H4"])
    def test_facility_has_lots(self, client: httpx.Client, facility: str) -> None:
        r = client.get("/api/core/lots", params={"facility": facility})
        assert r.status_code == 200, f"GET /lots?facility={facility}: {r.status_code} {r.text}"
        lots = r.json()
        assert isinstance(lots, list), f"Expected list, got {type(lots)}"
        assert len(lots) > 0, f"No lots found for {facility}"

    def test_total_lots(self, client: httpx.Client) -> None:
        r = client.get("/api/core/lots")
        assert r.status_code == 200
        lots = r.json()
        assert len(lots) >= 4, f"Expected >= 4 total lots, got {len(lots)}"


# ── Step 4: Run a plan ────────────────────────────────────────────

class TestStep4Plan:
    def test_run_plan(self, client: httpx.Client) -> None:
        r = client.post("/api/optimizer/plan/run", json={"mode": "live"}, timeout=60.0)
        assert r.status_code == 200, f"POST /plan/run: {r.status_code} {r.text}"
        body = r.json()

        # optimizer returns {"plan": {…}, "orders": […], "metrics": {…}}
        plan_obj = body.get("plan", body)
        plan_id = plan_obj.get("id") or plan_obj.get("plan_id") or body.get("plan_id")
        assert plan_id is not None, f"No plan id in response keys: {list(body.keys())}"

        TestStep4Plan._plan_id = plan_id
        TestStep4Plan._body = body


# ── Step 5: Validate orders ───────────────────────────────────────

class TestStep5Orders:
    def test_at_least_one_order(self, client: httpx.Client) -> None:
        plan_id = getattr(TestStep4Plan, '_plan_id', None)

        # Try core-api first (orders were persisted by optimizer)
        orders = None
        if plan_id:
            r = client.get("/api/core/orders", params={"plan_id": plan_id})
            if r.status_code == 200:
                orders = r.json()
                if not orders:
                    orders = None

        # Fallback: use orders from optimizer response
        if orders is None:
            body = getattr(TestStep4Plan, '_body', {})
            orders = body.get("orders", [])

        assert isinstance(orders, list)
        assert len(orders) >= 1, f"Expected >= 1 orders, got {len(orders)}"

        TestStep5Orders._orders = orders

    def test_all_orders_usable_positive(self, client: httpx.Client) -> None:
        orders = getattr(TestStep5Orders, '_orders', [])
        assert len(orders) > 0, "No orders to check (previous step failed?)"

        for o in orders:
            usable = o.get("usable", 0)
            assert usable > 0, (
                f"Order {o.get('id')} has usable={usable} "
                f"(drug={o.get('drug_code')}, src={o.get('src_facility_id')}→{o.get('dst_facility_id')})"
            )

    def test_no_controlled_drug_orders(self, client: httpx.Client) -> None:
        orders = getattr(TestStep5Orders, '_orders', [])
        assert len(orders) > 0, "No orders to check"

        for o in orders:
            drug_code = o.get("drug_code", "")
            assert drug_code not in CONTROLLED_DRUGS, (
                f"Order {o.get('id')} transfers controlled drug {drug_code}"
            )

    def test_audit_verify(self, client: httpx.Client) -> None:
        r = client.get("/api/core/audit/verify")
        assert r.status_code == 200, f"GET /audit/verify: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("ok") is True, f"Audit verification failed: {data}"
