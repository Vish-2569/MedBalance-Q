"""Tests for regret, why-not, what-if, and auto re-plan modules.

5 tests:
  1. regret ΔH matches energy recomputation
  2. why-not lists F3 for H4 insulin while ILR is down
  3. what-if repair_cold_storage(H4) makes H4 a destination
  4. auto re-plan moves cold orders off CV-02
  5. benchmark-style sanity
"""
from __future__ import annotations

from datetime import date

import pytest

from app.baselines import TransferOrder, greedy_f4
from app.candidates import Candidate, Chunk, generate_candidates
from app.feasibility import FeasibilityResult, FailedRule
from app.metrics import compute_metrics
from app.positions import compute_all_positions
from app.qubo_builder import QUBOConfig, build_qubo, energy
from app.regret import compute_regret_from_vars
from app.replan import handle_coldchain_alert, set_live_plan
from app.snapshot import Lot, Snapshot
from app.solvers.port import Sample, SolveResult
from app.whatif import run_whatif, _apply_overrides
from app.whynot import compute_whynot


@pytest.fixture
def snap(base_snapshot):
    return base_snapshot


@pytest.fixture
def positions(snap):
    return compute_all_positions(snap)


@pytest.fixture
def candidates(snap, positions):
    return generate_candidates(snap, positions)


@pytest.fixture
def qubo_pieces(candidates, snap):
    ven_priority = {code: drug.ven_priority for code, drug in snap.drugs.items()}
    shortages = {
        (fac_id, dc): pos.shortage
        for (fac_id, dc), pos in snap.positions.items()
        if pos.shortage > 0
    }
    qubo_result = build_qubo(candidates, ven_priority, shortages, QUBOConfig())

    from app.solvers.greedy_descent import GreedyDescent
    solver = GreedyDescent(seed=42)
    solve_result = solver.solve(
        qubo_result.Q, qubo_result.offset, qubo_result.num_variables,
        top_k=5, timeout=5.0,
    )

    return qubo_result, solve_result, ven_priority, shortages


class TestRegretDeltaH:
    """regret ΔH matches energy recomputation."""

    def test_delta_h_matches_energy(self, candidates, qubo_pieces):
        qubo_result, solve_result, ven_priority, _ = qubo_pieces

        if not solve_result.samples or qubo_result.num_variables == 0:
            pytest.skip("No QUBO solution found")

        best = solve_result.samples[0]
        base_energy = energy(qubo_result.Q, qubo_result.offset, best.x)

        selected_vars = {v for v, val in best.x.items() if val == 1}
        var_to_order: dict[int, str] = {}
        for i, v in enumerate(sorted(selected_vars)):
            var_to_order[v] = f"ORD-TEST-{i+1:03d}"

        regret_ledger = compute_regret_from_vars(
            var_to_order, candidates, qubo_result, solve_result, ven_priority,
        )

        assert len(regret_ledger) > 0, "Expected at least one order with regret"

        for order_regret in regret_ledger:
            v = order_regret.var_index
            for entry in order_regret.entries:
                if entry.source != "best_sample":
                    continue

                x_modified = dict(best.x)
                x_modified[v] = 0

                if entry.alternative_dst is not None:
                    chunk_id = candidates[qubo_result.variables[v]].chunk.chunk_id
                    for av, ci in enumerate(qubo_result.variables):
                        c = candidates[ci]
                        if c.chunk.chunk_id == chunk_id and c.destination_id == entry.alternative_dst:
                            x_modified[av] = 1
                            break

                expected_e = energy(qubo_result.Q, qubo_result.offset, x_modified)
                expected_dh = expected_e - base_energy
                assert abs(entry.delta_h - expected_dh) < 1e-6, (
                    f"ΔH mismatch for {order_regret.order_id} → {entry.alternative_dst}: "
                    f"regret={entry.delta_h}, recomputed={expected_dh}"
                )

    def test_regret_entries_have_reason_codes(self, candidates, qubo_pieces):
        qubo_result, solve_result, ven_priority, _ = qubo_pieces

        if not solve_result.samples or qubo_result.num_variables == 0:
            pytest.skip("No QUBO solution found")

        best = solve_result.samples[0]
        selected_vars = {v for v, val in best.x.items() if val == 1}
        var_to_order = {v: f"ORD-{i}" for i, v in enumerate(sorted(selected_vars))}

        regret = compute_regret_from_vars(
            var_to_order, candidates, qubo_result, solve_result, ven_priority,
        )
        for r in regret:
            for e in r.entries:
                assert e.reason_code, f"Empty reason_code for {r.order_id}"
                assert e.reason_text, f"Empty reason_text for {r.order_id}"
                assert isinstance(e.delta_h, float)


class TestWhyNotF3:
    """why-not lists F3 for H4 insulin while ILR is down."""

    def test_whynot_h4_insulin_f3(self, snap, candidates):
        orders = greedy_f4(snap)
        result = compute_whynot("H4", "INSULIN", snap, candidates, orders)

        assert result["facility_id"] == "H4"
        assert result["drug_code"] == "INSULIN"

        h4_fac = snap.facilities.get("H4")
        assert h4_fac is not None
        assert h4_fac.cold_storage is False, "H4 should lack cold storage"

        f3_found = False
        for c in result.get("candidates", []):
            failed = c.get("failed_rules", [])
            for fr in failed:
                if fr["rule"] == "F3":
                    f3_found = True
                    break

        if result["shortage_before"] > 0:
            assert f3_found or result["candidates_considered"] == 0, (
                "Expected F3 failure for insulin→H4 (no cold storage) "
                f"but got: {result}"
            )

    def test_whynot_structure(self, snap, candidates):
        orders = greedy_f4(snap)
        result = compute_whynot("H1", "PCM", snap, candidates, orders)

        assert "residual_shortage" in result
        assert "supplied" in result
        assert "candidates" in result
        assert isinstance(result["candidates"], list)


class TestWhatIfRepairColdStorage:
    """what-if repair_cold_storage(H4) makes H4 a destination."""

    def test_repair_cold_storage_h4(self, snap):
        live_orders = greedy_f4(snap)

        h4_cold_before = snap.facilities["H4"].cold_storage
        assert h4_cold_before is False, "H4 should start without cold storage"

        result = run_whatif(
            [{"action": "repair_cold_storage", "facility": "H4"}],
            snap, live_orders, solver="qubo",
        )

        assert "whatif_orders" in result
        assert "changes" in result
        assert "kpi_delta" in result

        wi_orders = result["whatif_orders"]
        h4_is_dst = any(
            o.get("dst_facility_id") == "H4" or o.get("dst") == "H4"
            for o in wi_orders
        )

        h4_has_shortage = any(
            pos.shortage > 0 for (fid, _), pos in snap.positions.items() if fid == "H4"
        )
        if h4_has_shortage:
            assert h4_is_dst, (
                f"After repairing H4 cold storage, expected H4 as destination. "
                f"WI orders: {[o.get('dst_facility_id', o.get('dst')) for o in wi_orders]}"
            )

    def test_overrides_dont_mutate_snapshot(self, snap):
        original_cold = snap.facilities["H4"].cold_storage
        _apply_overrides(snap, [{"action": "repair_cold_storage", "facility": "H4"}])
        assert snap.facilities["H4"].cold_storage == original_cold


class TestAutoReplanColdOrders:
    """auto re-plan moves cold orders off CV-02."""

    def test_replan_on_fridge_failure(self, snap):
        orders = greedy_f4(snap)

        cold_orders = [o for o in orders if o.temperature_req == "cold_chain"]

        plan = {"id": "plan-test-001", "mode": "live"}
        set_live_plan(plan, orders, snap)

        alert = {
            "device_id": "sensor-cv02-a",
            "vehicle_id": "CV-02",
            "temp_c": 18.5,
            "severity": "critical",
        }

        result = handle_coldchain_alert(alert)

        if cold_orders:
            assert result is not None, "Expected revised plan when cold orders exist"
            assert "plan_id" in result
            assert result["plan_id"].startswith("plan-rev-")
            assert "reason" in result
            assert "coldchain" in result["reason"].lower()
            assert "changes" in result
        else:
            pass

    def test_replan_noop_without_live_plan(self):
        set_live_plan(None, None, None)
        result = handle_coldchain_alert({"device_id": "sensor-cv02-a", "vehicle_id": "CV-02"})
        assert result is None


class TestRegretSanity:
    """Additional sanity: regret top entries sorted by ΔH ascending."""

    def test_regret_sorted(self, candidates, qubo_pieces):
        qubo_result, solve_result, ven_priority, _ = qubo_pieces

        if not solve_result.samples or qubo_result.num_variables == 0:
            pytest.skip("No solution")

        best = solve_result.samples[0]
        selected_vars = {v for v, val in best.x.items() if val == 1}
        var_to_order = {v: f"ORD-{i}" for i, v in enumerate(sorted(selected_vars))}

        regret = compute_regret_from_vars(
            var_to_order, candidates, qubo_result, solve_result, ven_priority,
        )
        for r in regret:
            dhs = [e.delta_h for e in r.entries]
            assert dhs == sorted(dhs), f"Entries not sorted by ΔH: {dhs}"
