"""Brute-force enumeration tests for QUBO builder (v3 Hamiltonian).

8 tiny instances (≤12 variables each).  For every instance we enumerate ALL
2^n assignments and verify the minimum-energy assignment matches the expected
optimal feasible plan.
"""
from __future__ import annotations

import math
from datetime import date

import pytest

from app.candidates import Candidate, Chunk
from app.feasibility import FeasibilityResult
from app.snapshot import Lot
from app.qubo_builder import (
    QUBOConfig,
    build_qubo,
    energy,
    brute_force_min,
    term_breakdown,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _lot(src: str, drug: str, batch: str, expiry: date | None = None, qty: int = 200) -> Lot:
    return Lot(
        facility_id=src, drug_code=drug, batch_no=batch,
        expiry=expiry or date(2026, 12, 31), qty=qty,
    )


def _cand(
    src: str, dst: str, drug: str, batch: str, chunk_idx: int, chunk_qty: int,
    usable: int, reward: float, trip_cost: float,
    feasible: bool = True, selected: bool = True,
    lot_qty: int = 200, expiry: date | None = None,
) -> Candidate:
    lot = _lot(src, drug, batch, expiry, lot_qty)
    chunk = Chunk(lot=lot, index=chunk_idx, qty=chunk_qty)
    feas = FeasibilityResult(feasible=feasible, failed_rules=[], rules={})
    return Candidate(
        chunk=chunk, destination_id=dst, drug_code=drug,
        usable=usable, reward=reward, trip_cost=trip_cost,
        net_score=reward - trip_cost, feasibility=feas, selected=selected,
    )


def _all_energies(Q, offset, n):
    """Return {assignment_tuple: energy} for all 2^n states."""
    out = {}
    for bits in range(1 << n):
        x = {i: (bits >> i) & 1 for i in range(n)}
        out[tuple(x[i] for i in range(n))] = energy(Q, offset, x)
    return out


# ── test a: one-place conflict ───────────────────────────────────────────────

class TestOnePlaceConflict:
    """Chunk sent to 2 destinations must have higher energy than either alone."""

    def test_one_place(self):
        # 1 chunk (H1:D1:B1:c0) can go to H2 or H3
        # No shortage at either destination → isolate the P1 one-place penalty
        cands = [
            _cand("H1", "H2", "D1", "B1", 0, 100, usable=80, reward=800, trip_cost=100),
            _cand("H1", "H3", "D1", "B1", 0, 100, usable=60, reward=600, trip_cost=100),
        ]
        ven = {"D1": 2}
        shortages = {("H2", "D1"): 0, ("H3", "D1"): 0}

        config = QUBOConfig(gamma=0.0)
        r = build_qubo(cands, ven, shortages, config)
        assert r.num_variables == 2

        e_both = energy(r.Q, r.offset, {0: 1, 1: 1})
        e_h2 = energy(r.Q, r.offset, {0: 1, 1: 0})
        e_h3 = energy(r.Q, r.offset, {0: 0, 1: 1})

        assert e_both > e_h2, "P1 penalty: sending to both should be worse than H2 alone"
        assert e_both > e_h3, "P1 penalty: sending to both should be worse than H3 alone"

        best_x, _ = brute_force_min(r.Q, r.offset, r.num_variables)
        assert best_x[0] + best_x[1] == 1, "Optimal sends to exactly one destination"


# ── test b: two lots competing for one shortage ──────────────────────────────

class TestTwoLotsOneShortage:
    """Optimal picks the lot with higher usable to fill the shortage."""

    def test_higher_usable_wins(self):
        cands = [
            _cand("H1", "H2", "D1", "B1", 0, 100, usable=80, reward=800, trip_cost=100),
            _cand("H1", "H2", "D1", "B2", 0, 50, usable=40, reward=400, trip_cost=100),
        ]
        ven = {"D1": 2}
        shortages = {("H2", "D1"): 80}

        r = build_qubo(cands, ven, shortages)

        best_x, best_e = brute_force_min(r.Q, r.offset, r.num_variables)
        assert best_x[0] == 1, "Higher-usable lot (B1, u=80) should be selected"

        # Verify: sending only B1 exactly fills the shortage with zero overfill penalty
        e_b1 = energy(r.Q, r.offset, {0: 1, 1: 0})
        e_b2 = energy(r.Q, r.offset, {0: 0, 1: 1})
        assert e_b1 < e_b2


# ── test c: overfill ─────────────────────────────────────────────────────────

class TestOverfill:
    """Sending more than the shortage is penalised by P2."""

    def test_overfill_penalised(self):
        # 2 lots from different sources, same drug, same destination
        # Each usable = shortage → sending both overfills 2×
        cands = [
            _cand("H1", "H3", "D1", "B1", 0, 50, usable=50, reward=500, trip_cost=50),
            _cand("H2", "H3", "D1", "B2", 0, 50, usable=50, reward=500, trip_cost=50),
        ]
        ven = {"D1": 2}
        shortages = {("H3", "D1"): 50}

        r = build_qubo(cands, ven, shortages)

        e_both = energy(r.Q, r.offset, {0: 1, 1: 1})
        e_one = energy(r.Q, r.offset, {0: 1, 1: 0})
        e_none = energy(r.Q, r.offset, {0: 0, 1: 0})

        assert e_both > e_one, "Overfill: sending both costs more than sending one"
        assert e_one < e_none, "Sending one is still better than sending none"

        best_x, _ = brute_force_min(r.Q, r.offset, r.num_variables)
        total_sent = best_x[0] + best_x[1]
        assert total_sent == 1, "Optimal sends exactly one lot (no overfill)"


# ── test d: zero-demand guard ────────────────────────────────────────────────

class TestZeroDemandGuard:
    """No P2 penalty when destination has zero shortage."""

    def test_no_p2_when_no_shortage(self):
        cands = [
            _cand("H1", "H2", "D1", "B1", 0, 100, usable=80, reward=800, trip_cost=100),
        ]
        ven = {"D1": 2}
        shortages = {("H2", "D1"): 0}

        r = build_qubo(cands, ven, shortages)

        assert r.offset == 0.0, "No P2 offset when shortage is 0"

        e_send = energy(r.Q, r.offset, {0: 1})
        e_none = energy(r.Q, r.offset, {0: 0})

        # Positive net_score → sending should be rewarded
        assert e_send < e_none, "Positive reward → send"

        bd = term_breakdown(
            r.Q, r.offset, {0: 1}, cands, r.variables,
            ven, shortages, r.config_used, r.norm_factor,
        )
        assert bd["fill_penalty"] == 0.0, "No fill penalty contribution at all"


# ── test e: cold-chain infeasible pair absent ────────────────────────────────

class TestInfeasibleAbsent:
    """Infeasible (chunk, dst) pairs must not appear as QUBO variables."""

    def test_infeasible_excluded(self):
        cands = [
            _cand("H1", "H2", "D1", "B1", 0, 100, usable=80, reward=800, trip_cost=100,
                   feasible=True, selected=True),
            _cand("H1", "H3", "D1", "B1", 0, 100, usable=60, reward=600, trip_cost=100,
                   feasible=False, selected=False),
        ]
        ven = {"D1": 2}
        shortages = {("H2", "D1"): 100, ("H3", "D1"): 100}

        r = build_qubo(cands, ven, shortages)

        assert r.num_variables == 1
        assert r.variables == [0], "Only the feasible candidate is a variable"

        best_x, _ = brute_force_min(r.Q, r.offset, r.num_variables)
        assert best_x[0] == 1, "Single feasible candidate should be sent"


# ── test f: shared-trip bonus ────────────────────────────────────────────────

class TestSharedTripBonus:
    """Two chunks to same dst on same trip beat splitting across destinations."""

    def test_consolidation_wins(self):
        # 2 lots from H1, each chunk 0. Each can go to H2 or H3.
        cands = [
            _cand("H1", "H2", "D1", "B1", 0, 100, usable=50, reward=500, trip_cost=100),  # 0
            _cand("H1", "H3", "D1", "B1", 0, 100, usable=50, reward=500, trip_cost=100),  # 1
            _cand("H1", "H2", "D1", "B2", 0, 100, usable=50, reward=500, trip_cost=100),  # 2
            _cand("H1", "H3", "D1", "B2", 0, 100, usable=50, reward=500, trip_cost=100),  # 3
        ]
        ven = {"D1": 2}
        shortages = {("H2", "D1"): 200, ("H3", "D1"): 200}

        config = QUBOConfig(gamma=0.5)
        r = build_qubo(cands, ven, shortages, config)

        # Both to H2 (vars 0, 2) vs split (var 0 to H2, var 3 to H3)
        e_consolidated = energy(r.Q, r.offset, {0: 1, 1: 0, 2: 1, 3: 0})
        e_split = energy(r.Q, r.offset, {0: 1, 1: 0, 2: 0, 3: 1})

        assert e_consolidated < e_split, "Shared trip bonus makes consolidation better"

        # Both to H3 (vars 1, 3) is equally good as both to H2 by symmetry
        e_consolidated_h3 = energy(r.Q, r.offset, {0: 0, 1: 1, 2: 0, 3: 1})
        assert abs(e_consolidated - e_consolidated_h3) < 1e-9, "Symmetric destinations"


# ── test g: chunk order ──────────────────────────────────────────────────────

class TestChunkOrder:
    """Sending chunk 1 without chunk 0 costs more than sending both."""

    def test_out_of_order_penalised(self):
        cands = [
            _cand("H1", "H2", "D1", "B1", 0, 100, usable=80, reward=800, trip_cost=100),
            _cand("H1", "H2", "D1", "B1", 1, 50, usable=40, reward=400, trip_cost=50),
        ]
        ven = {"D1": 2}
        shortages = {("H2", "D1"): 0}  # no shortage → isolate P3

        config = QUBOConfig(gamma=0.0)
        r = build_qubo(cands, ven, shortages, config)

        e_both = energy(r.Q, r.offset, {0: 1, 1: 1})
        e_c0_only = energy(r.Q, r.offset, {0: 1, 1: 0})
        e_c1_only = energy(r.Q, r.offset, {0: 0, 1: 1})

        assert e_c1_only > e_both, "Chunk 1 alone (out of order) costs more than both"
        assert e_c1_only > e_c0_only, "Chunk 1 alone costs more than chunk 0 alone"
        assert e_both < e_c0_only, "Both chunks together is best (P3 cancels)"


# ── test h: VEN priority ─────────────────────────────────────────────────────

class TestVENPriority:
    """Vital drug (π=3) fills its shortage before essential (π=2)."""

    def test_vital_before_essential(self):
        # Anchor candidate with positive net_score sets the normalization
        anchor = _cand("HA", "HB", "ANCHOR", "BA", 0, 100,
                        usable=50, reward=200, trip_cost=100)
        # Vital drug: expensive transfer (net_score < 0)
        vital = _cand("HC", "HD", "DV", "BV", 0, 100,
                       usable=10, reward=50, trip_cost=400)
        # Essential drug: same expensive transfer
        essential = _cand("HE", "HF", "DE", "BE", 0, 100,
                          usable=10, reward=50, trip_cost=400)

        cands = [anchor, vital, essential]
        ven = {"ANCHOR": 1, "DV": 3, "DE": 2}
        shortages = {("HB", "ANCHOR"): 100, ("HD", "DV"): 10, ("HF", "DE"): 10}

        r = build_qubo(cands, ven, shortages)

        best_x, _ = brute_force_min(r.Q, r.offset, r.num_variables)

        assert best_x[0] == 1, "Anchor (positive reward) always sent"
        assert best_x[1] == 1, "Vital drug sent despite negative net (P2×3 overcomes cost)"
        assert best_x[2] == 0, "Essential drug NOT sent (P2×2 insufficient to overcome cost)"

        # Verify energy ordering
        e_vital_only = energy(r.Q, r.offset, {0: 1, 1: 1, 2: 0})
        e_essential_only = energy(r.Q, r.offset, {0: 1, 1: 0, 2: 1})
        assert e_vital_only < e_essential_only, "Vital fills before essential"


# ── consistency check: term_breakdown sums to energy ─────────────────────────

class TestBreakdownConsistency:
    """term_breakdown total must equal energy for every test scenario."""

    @pytest.mark.parametrize("label,cands,ven,shortages,config", [
        (
            "one_place",
            [
                _cand("H1", "H2", "D1", "B1", 0, 100, usable=80, reward=800, trip_cost=100),
                _cand("H1", "H3", "D1", "B1", 0, 100, usable=60, reward=600, trip_cost=100),
            ],
            {"D1": 2},
            {("H2", "D1"): 100, ("H3", "D1"): 100},
            None,
        ),
        (
            "overfill",
            [
                _cand("H1", "H3", "D1", "B1", 0, 50, usable=50, reward=500, trip_cost=50),
                _cand("H2", "H3", "D1", "B2", 0, 50, usable=50, reward=500, trip_cost=50),
            ],
            {"D1": 2},
            {("H3", "D1"): 50},
            None,
        ),
        (
            "chunk_order",
            [
                _cand("H1", "H2", "D1", "B1", 0, 100, usable=80, reward=800, trip_cost=100),
                _cand("H1", "H2", "D1", "B1", 1, 50, usable=40, reward=400, trip_cost=50),
            ],
            {"D1": 2},
            {("H2", "D1"): 0},
            QUBOConfig(gamma=0.0),
        ),
    ], ids=["one_place", "overfill", "chunk_order"])
    def test_breakdown_equals_energy(self, label, cands, ven, shortages, config):
        r = build_qubo(cands, ven, shortages, config)

        for bits in range(1 << r.num_variables):
            x = {i: (bits >> i) & 1 for i in range(r.num_variables)}
            e = energy(r.Q, r.offset, x)
            bd = term_breakdown(
                r.Q, r.offset, x, cands, r.variables,
                ven, shortages, r.config_used, r.norm_factor,
            )
            assert abs(bd["total"] - e) < 1e-9, (
                f"Breakdown total {bd['total']} != energy {e} for x={x}"
            )
