"""Tests for solver chain, validator, and QUBO integration."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from app.candidates import Candidate, Chunk
from app.feasibility import FeasibilityResult
from app.snapshot import Snapshot, Lot, Drug, Facility, Route, Vehicle, Position
from app.qubo_builder import build_qubo, QUBOConfig, energy
from app.solvers.port import Sample, SolveResult
from app.solvers.greedy_descent import GreedyDescent
from app.solvers.chain import solve_chain, EVIDENCE_DIR
from app.validator import apply_plan, repair, Violation, ValidatedOrder


# ── helpers ──────────────────────────────────────────────────────────────────

def _lot(src: str, drug: str, batch: str, expiry=None, qty=200):
    return Lot(src, drug, batch, expiry or date(2026, 12, 31), qty)


def _cand(src, dst, drug, batch, chunk_idx, chunk_qty, usable, reward, trip_cost,
          feasible=True, selected=True, lot_qty=200, expiry=None):
    lot = _lot(src, drug, batch, expiry, lot_qty)
    chunk = Chunk(lot=lot, index=chunk_idx, qty=chunk_qty)
    feas = FeasibilityResult(feasible=feasible, failed_rules=[], rules={})
    return Candidate(chunk=chunk, destination_id=dst, drug_code=drug,
                     usable=usable, reward=reward, trip_cost=trip_cost,
                     net_score=reward - trip_cost, feasibility=feas, selected=selected)


def _mini_snapshot(today=None):
    """Minimal snapshot for validator tests."""
    today = today or date(2026, 11, 1)
    snap = Snapshot(today=today)
    snap.facilities = {
        "H1": Facility("H1", "Hospital 1", "DH", True),
        "H2": Facility("H2", "Hospital 2", "TH", True),
        "H3": Facility("H3", "CHC", "CHC", False),
    }
    snap.drugs = {
        "D1": Drug("D1", "Drug1", "E", "tablet", 10, False, False, 30, 10.0),
        "DV": Drug("DV", "VitalDrug", "V", "vial", 1, False, False, 30, 50.0),
        "COLD": Drug("COLD", "ColdDrug", "E", "vial", 1, True, False, 30, 100.0),
        "CTRL": Drug("CTRL", "Controlled", "V", "amp", 5, False, True, 60, 35.0),
    }
    snap.routes = {
        ("H1", "H2"): Route("H1", "H2", 10.0, 0.5, True, 50.0, 120.0),
        ("H2", "H1"): Route("H2", "H1", 10.0, 0.5, True, 50.0, 120.0),
        ("H1", "H3"): Route("H1", "H3", 15.0, 1.0, False, 70.0, 150.0),
        ("H2", "H3"): Route("H2", "H3", 12.0, 0.8, False, 60.0, 130.0),
    }
    snap.vehicles = [
        Vehicle("V1", "Cold Van", True, 5000),
        Vehicle("V2", "Van", False, 10000),
    ]
    snap.lots = [
        Lot("H1", "D1", "B1", date(2026, 12, 15), 500),
        Lot("H2", "D1", "B2", date(2026, 12, 20), 300),
        Lot("H1", "DV", "BV1", date(2026, 12, 10), 100),
    ]
    snap.lots_by_fd = {}
    for lot in snap.lots:
        snap.lots_by_fd.setdefault((lot.facility_id, lot.drug_code), []).append(lot)
    snap.positions = {
        ("H1", "D1"): Position("H1", "D1", 400, 100, 50, 0, 10.0, 21),
        ("H2", "D1"): Position("H2", "D1", 100, 200, 30, 110, 15.0, 21),
        ("H3", "D1"): Position("H3", "D1", 0, 0, 0, 200, 8.0, 21),
        ("H1", "DV"): Position("H1", "DV", 80, 20, 10, 0, 3.0, 21),
        ("H2", "DV"): Position("H2", "DV", 0, 0, 0, 50, 2.0, 21),
    }
    snap.policies = {}
    return snap


# ── solver chain tests ───────────────────────────────────────────────────────

class TestSolverChain:
    """Solver chain falls through tiers correctly."""

    def test_greedy_descent_works(self):
        cands = [
            _cand("H1", "H2", "D1", "B1", 0, 100, usable=80, reward=800, trip_cost=100),
            _cand("H1", "H3", "D1", "B1", 0, 100, usable=60, reward=600, trip_cost=100),
        ]
        ven = {"D1": 2}
        shortages = {("H2", "D1"): 100, ("H3", "D1"): 100}

        r = build_qubo(cands, ven, shortages, QUBOConfig(gamma=0.0))
        solver = GreedyDescent(restarts=20, seed=42)
        result = solver.solve(r.Q, r.offset, r.num_variables, top_k=3)

        assert result.tier == "greedy-descent"
        assert len(result.samples) > 0
        assert result.error is None

    def test_chain_falls_through_to_greedy(self):
        """With no API keys, chain falls through to greedy descent."""
        cands = [
            _cand("H1", "H2", "D1", "B1", 0, 100, usable=80, reward=800, trip_cost=100),
        ]
        r = build_qubo(cands, {"D1": 2}, {("H2", "D1"): 100}, QUBOConfig(gamma=0.0))

        tiers = [GreedyDescent(restarts=10, seed=42)]
        result = solve_chain(r.Q, r.offset, r.num_variables, tiers=tiers)

        assert result.tier == "greedy-descent"
        assert len(result.samples) > 0

    def test_chain_records_attempts(self):
        cands = [
            _cand("H1", "H2", "D1", "B1", 0, 100, usable=80, reward=800, trip_cost=100),
        ]
        r = build_qubo(cands, {"D1": 2}, {("H2", "D1"): 100}, QUBOConfig(gamma=0.0))

        tiers = [GreedyDescent(restarts=10, seed=42)]
        result = solve_chain(r.Q, r.offset, r.num_variables, tiers=tiers)

        assert "attempts" in result.meta
        assert len(result.meta["attempts"]) >= 1

    def test_evidence_json_written(self, tmp_path):
        cands = [
            _cand("H1", "H2", "D1", "B1", 0, 100, usable=80, reward=800, trip_cost=100),
        ]
        r = build_qubo(cands, {"D1": 2}, {("H2", "D1"): 100}, QUBOConfig(gamma=0.0))

        with patch("app.solvers.chain.EVIDENCE_DIR", tmp_path):
            tiers = [GreedyDescent(restarts=5, seed=42)]
            solve_chain(r.Q, r.offset, r.num_variables, tiers=tiers)

        files = list(tmp_path.glob("*.json"))
        assert len(files) >= 1

        evidence = json.loads(files[0].read_text())
        assert "attempts" in evidence
        assert "winner" in evidence
        assert evidence["winner"]["tier"] == "greedy-descent"
        assert evidence["n_vars"] == r.num_variables


# ── validator tests ──────────────────────────────────────────────────────────

class TestValidator:

    def test_valid_transfer(self):
        snap = _mini_snapshot()
        cand = _cand("H1", "H2", "D1", "B1", 0, 50, usable=50, reward=500, trip_cost=50,
                      lot_qty=500, expiry=date(2026, 12, 15))
        result = apply_plan(snap, [(0, cand)])

        valid_orders = [o for o in result.orders if not o.dropped]
        assert len(valid_orders) == 1
        assert valid_orders[0].qty <= 50

    def test_catches_double_ship(self):
        snap = _mini_snapshot()
        cand1 = _cand("H1", "H2", "D1", "B1", 0, 50, usable=50, reward=500, trip_cost=50,
                       lot_qty=500, expiry=date(2026, 12, 15))
        cand2 = _cand("H1", "H3", "D1", "B1", 0, 50, usable=40, reward=400, trip_cost=70,
                       lot_qty=500, expiry=date(2026, 12, 15))
        result = apply_plan(snap, [(0, cand1), (1, cand2)])

        double_ship = [v for v in result.violations if v.rule == "double_ship"]
        assert len(double_ship) == 1

    def test_catches_negative_stock(self):
        snap = _mini_snapshot()
        # Lot B1 has 500 units, try to send 600
        cand = _cand("H1", "H2", "D1", "B1", 0, 600, usable=500, reward=5000, trip_cost=50,
                      lot_qty=500, expiry=date(2026, 12, 15))
        cand.chunk = Chunk(lot=_lot("H1", "D1", "B1", date(2026, 12, 15), 500),
                           index=0, qty=600)
        result = apply_plan(snap, [(0, cand)])

        neg_stock = [v for v in result.violations if v.rule == "negative_stock"]
        assert len(neg_stock) == 1

    def test_catches_controlled_drug(self):
        snap = _mini_snapshot()
        snap.lots.append(Lot("H1", "CTRL", "BC1", date(2027, 6, 1), 50))
        snap.lots_by_fd.setdefault(("H1", "CTRL"), []).append(
            Lot("H1", "CTRL", "BC1", date(2027, 6, 1), 50)
        )
        cand = _cand("H1", "H2", "CTRL", "BC1", 0, 10, usable=10, reward=350, trip_cost=50,
                      lot_qty=50, expiry=date(2027, 6, 1))
        result = apply_plan(snap, [(0, cand)])

        controlled = [v for v in result.violations if v.rule == "controlled"]
        assert len(controlled) == 1
        assert result.orders[0].dropped

    def test_trims_usable(self):
        snap = _mini_snapshot()
        # Set low dst rate so realised usable < planned usable
        snap.positions[("H2", "D1")] = Position("H2", "D1", 100, 200, 30, 110, 0.5, 21)

        cand = _cand("H1", "H2", "D1", "B1", 0, 100, usable=100, reward=1000, trip_cost=50,
                      lot_qty=500, expiry=date(2026, 12, 15))
        result = apply_plan(snap, [(0, cand)])

        valid = [o for o in result.orders if not o.dropped]
        if valid:
            assert valid[0].usable <= 100
            if valid[0].trimmed:
                assert result.trimmed_count > 0


class TestRepair:

    def test_drops_lowest_reward(self):
        violations = [Violation(0, "double_ship", "test"), Violation(1, "double_ship", "test")]
        cands = [
            _cand("H1", "H2", "D1", "B1", 0, 100, usable=80, reward=800, trip_cost=100),
            _cand("H1", "H3", "D1", "B2", 0, 50, usable=40, reward=200, trip_cost=100),
        ]
        result = repair({}, 0.0, violations, cands, [0, 1], max_attempts=1)
        # Lower reward (B2, net=100) dropped first; higher reward kept
        assert 0 in result
        assert 1 not in result


# ── integration: QUBO → solve → validate ─────────────────────────────────────

class TestQuboIntegration:

    def test_full_pipeline(self):
        snap = _mini_snapshot()

        cands = [
            _cand("H1", "H3", "D1", "B1", 0, 100, usable=80, reward=800, trip_cost=70,
                   lot_qty=500, expiry=date(2026, 12, 15)),
            _cand("H2", "H3", "D1", "B2", 0, 80, usable=60, reward=600, trip_cost=60,
                   lot_qty=300, expiry=date(2026, 12, 20)),
        ]
        ven = {"D1": 2}
        shortages = {("H3", "D1"): 200}

        r = build_qubo(cands, ven, shortages, QUBOConfig(gamma=0.0))

        solver = GreedyDescent(restarts=20, seed=42)
        solve_result = solver.solve(r.Q, r.offset, r.num_variables)
        assert solve_result.samples

        best = solve_result.samples[0]
        selected = []
        for v, val in best.x.items():
            if val == 1 and v < len(r.variables):
                ci = r.variables[v]
                selected.append((ci, cands[ci]))

        val_result = apply_plan(snap, selected)
        valid_orders = [o for o in val_result.orders if not o.dropped]
        assert len(valid_orders) >= 1


# ── API integration test ─────────────────────────────────────────────────────

class TestAPIIntegration:

    def test_plan_run_qubo(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.post("/plan/run", json={"mode": "live", "solver": "qubo"})
        assert resp.status_code == 200
        data = resp.json()

        assert "plan" in data
        assert "orders" in data
        assert "metrics" in data
        assert data["plan"]["solver_tier"] in (
            "greedy-descent", "neal-sa", "qpiai-local", "qpiai-platform",
            "greedy-f4-fallback", "qubo-empty", "greedy-f4",
        )

    def test_plan_run_greedy_f4(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.post("/plan/run", json={"mode": "live", "solver": "greedy_f4"})
        assert resp.status_code == 200
        assert resp.json()["plan"]["solver_tier"] == "greedy-f4"
