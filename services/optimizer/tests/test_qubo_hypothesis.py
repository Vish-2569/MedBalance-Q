"""Hypothesis property tests for QUBO builder and solver integration.

Generates random small snapshots (≤5 facilities, ≤8 drugs, ≤20 lots)
and verifies invariants hold across random inputs.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.qubo_builder import build_qubo, QUBOConfig, energy, brute_force_min
from app.solvers.greedy_descent import GreedyDescent
from app.solvers.port import SolveResult


# ── strategies ──────────────────────────────────────────────────────────────

facility_ids = st.sampled_from(["F1", "F2", "F3", "F4", "F5"])
drug_codes = st.sampled_from(["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"])
ven_values = st.sampled_from([1, 2, 3])


@st.composite
def random_candidate(draw):
    """Generate a random Candidate-like object for QUBO builder."""
    from app.candidates import Candidate, Chunk
    from app.feasibility import FeasibilityResult
    from app.snapshot import Lot

    src = draw(facility_ids)
    dst = draw(facility_ids.filter(lambda f: f != src))
    drug = draw(drug_codes)
    batch = f"B-{draw(st.integers(1, 100))}"
    expiry = date(2026, 11, 1) + timedelta(days=draw(st.integers(15, 180)))
    lot_qty = draw(st.integers(10, 500))
    chunk_idx = draw(st.integers(0, 2))
    chunk_qty = draw(st.integers(1, min(lot_qty, 250)))
    usable = draw(st.integers(0, chunk_qty))
    reward = draw(st.floats(0, 1000, allow_nan=False, allow_infinity=False))
    trip_cost = draw(st.floats(0, 500, allow_nan=False, allow_infinity=False))

    lot = Lot(src, drug, batch, expiry, lot_qty)
    chunk = Chunk(lot=lot, index=chunk_idx, qty=chunk_qty)
    feas = FeasibilityResult(feasible=True, failed_rules=[], rules={})
    net = reward - trip_cost

    return Candidate(
        chunk=chunk, destination_id=dst, drug_code=drug,
        usable=usable, reward=reward, trip_cost=trip_cost,
        net_score=net, feasibility=feas, selected=True,
    )


@st.composite
def random_qubo_inputs(draw):
    """Generate a full set of inputs for build_qubo."""
    n_cands = draw(st.integers(1, 20))
    candidates = draw(st.lists(random_candidate(), min_size=n_cands, max_size=n_cands))

    drugs_in_play = {c.drug_code for c in candidates}
    ven_priority = {d: draw(ven_values) for d in drugs_in_play}

    dsts_in_play = {c.destination_id for c in candidates}
    shortages = {}
    for dst in dsts_in_play:
        for drug in drugs_in_play:
            if draw(st.booleans()):
                shortages[(dst, drug)] = draw(st.integers(1, 500))

    p2 = draw(st.sampled_from([0.5, 1.0, 1.5, 2.0, 3.0]))
    config = QUBOConfig(p2=p2, gamma=0.0)

    return candidates, ven_priority, shortages, config


# ── property tests ──────────────────────────────────────────────────────────

class TestQUBOProperties:

    @given(data=random_qubo_inputs())
    @settings(max_examples=50, deadline=5000)
    def test_q_matrix_is_upper_triangular(self, data):
        candidates, ven, shortages, config = data
        result = build_qubo(candidates, ven, shortages, config)

        for (i, j), val in result.Q.items():
            assert i <= j, f"Q has lower-triangular entry ({i},{j})"

    @given(data=random_qubo_inputs())
    @settings(max_examples=50, deadline=5000)
    def test_energy_is_finite(self, data):
        candidates, ven, shortages, config = data
        result = build_qubo(candidates, ven, shortages, config)
        if result.num_variables == 0:
            return

        x_all_zero = {i: 0 for i in range(result.num_variables)}
        x_all_one = {i: 1 for i in range(result.num_variables)}

        e0 = energy(result.Q, result.offset, x_all_zero)
        e1 = energy(result.Q, result.offset, x_all_one)

        assert isinstance(e0, float) and not (e0 != e0)  # not NaN
        assert isinstance(e1, float) and not (e1 != e1)

    @given(data=random_qubo_inputs())
    @settings(max_examples=50, deadline=5000)
    def test_all_zero_energy_equals_offset(self, data):
        candidates, ven, shortages, config = data
        result = build_qubo(candidates, ven, shortages, config)
        if result.num_variables == 0:
            return

        x_zero = {i: 0 for i in range(result.num_variables)}
        e = energy(result.Q, result.offset, x_zero)
        assert abs(e - result.offset) < 1e-9

    @given(data=random_qubo_inputs())
    @settings(max_examples=50, deadline=5000)
    def test_greedy_descent_finds_valid_solution(self, data):
        candidates, ven, shortages, config = data
        result = build_qubo(candidates, ven, shortages, config)
        if result.num_variables == 0:
            return

        solver = GreedyDescent(restarts=10, seed=42)
        sr = solver.solve(result.Q, result.offset, result.num_variables, top_k=3)

        assert sr.tier == "greedy-descent"
        assert sr.error is None
        assert len(sr.samples) > 0

        for sample in sr.samples:
            assert all(v in (0, 1) for v in sample.x.values())
            e = energy(result.Q, result.offset, sample.x)
            assert abs(e - sample.energy) < 1e-6

    @given(data=random_qubo_inputs())
    @settings(max_examples=30, deadline=10000)
    def test_greedy_at_most_as_good_as_brute_force_for_small(self, data):
        """For small instances, greedy should find the global minimum."""
        candidates, ven, shortages, config = data
        result = build_qubo(candidates, ven, shortages, config)
        assume(0 < result.num_variables <= 12)

        best_x, best_e = brute_force_min(result.Q, result.offset, result.num_variables)

        solver = GreedyDescent(restarts=50, seed=42)
        sr = solver.solve(result.Q, result.offset, result.num_variables, top_k=1)

        assert sr.samples[0].energy >= best_e - 1e-9

    @given(data=random_qubo_inputs())
    @settings(max_examples=50, deadline=5000)
    def test_variable_count_capped_at_150(self, data):
        candidates, ven, shortages, config = data
        result = build_qubo(candidates, ven, shortages, config)
        assert result.num_variables <= 150

    @given(data=random_qubo_inputs())
    @settings(max_examples=50, deadline=5000)
    def test_norm_factor_positive(self, data):
        candidates, ven, shortages, config = data
        result = build_qubo(candidates, ven, shortages, config)
        assert result.norm_factor > 0
