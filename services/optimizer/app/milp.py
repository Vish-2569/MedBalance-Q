"""OR-Tools CP-SAT exact baseline for the same allocation problem.

Binary per candidate, one-place constraint, shortage fill with linearised
piecewise reward capped at n, shared-trip binary per (src,dst).
Maximises the same normalised objective as the QUBO. Time limit 20s.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ortools.sat.python import cp_model

from medbal_common.logging import get_logger

from .candidates import Candidate

log = get_logger("optimizer.milp")

SCALE = 10000


@dataclass
class MILPResult:
    objective: float
    status: str  # OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN
    selected_indices: list[int]
    time_ms: float
    gap: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def solve_milp(
    candidates: list[Candidate],
    ven_priority: dict[str, int],
    shortages: dict[tuple[str, str], int],
    norm_factor: float,
    *,
    time_limit_s: float = 20.0,
    p1: float = 2.0,
    p2: float = 1.5,
    p3: float = 1.0,
    gamma: float = 0.0,
) -> MILPResult:
    """Solve the allocation as a CP-SAT model. Returns exact optimum."""
    t0 = time.perf_counter()

    active = [
        (ci, c)
        for ci, c in enumerate(candidates)
        if c.feasibility.feasible and c.selected
    ]

    if not active:
        ms = (time.perf_counter() - t0) * 1000
        return MILPResult(
            objective=0, status="OPTIMAL", selected_indices=[],
            time_ms=ms,
        )

    model = cp_model.CpModel()

    x: dict[int, Any] = {}
    ci_to_var: dict[int, int] = {}
    for v, (ci, _c) in enumerate(active):
        x[v] = model.new_bool_var(f"x_{v}")
        ci_to_var[ci] = v

    n = len(active)
    obj_terms: list[Any] = []

    # Reward: maximise Σ (net_score / norm_factor) * x_i
    for v, (_, c) in enumerate(active):
        scaled_reward = int(round(c.net_score / norm_factor * SCALE))
        obj_terms.append(scaled_reward * x[v])

    # P1: one-place — at most one destination per chunk
    by_chunk: dict[str, list[int]] = {}
    for v, (_, c) in enumerate(active):
        by_chunk.setdefault(c.chunk.chunk_id, []).append(v)

    for _cid, vs in by_chunk.items():
        if len(vs) > 1:
            model.add(sum(x[v] for v in vs) <= 1)

    # P2: shortage fill — supply ≤ shortage (linearised cap)
    by_dst_drug: dict[tuple[str, str], list[tuple[int, Candidate]]] = {}
    for v, (_, c) in enumerate(active):
        by_dst_drug.setdefault((c.destination_id, c.drug_code), []).append((v, c))

    for (dst, drug), items in by_dst_drug.items():
        n_short = shortages.get((dst, drug), 0)
        if n_short <= 0:
            continue
        pi = ven_priority.get(drug, 1)
        total_supply = sum(c.usable * x[v] for v, c in items)
        model.add(total_supply <= n_short)
        scaled_bonus = int(round(p2 * pi * SCALE / max(n_short, 1)))
        for v, c in items:
            obj_terms.append(scaled_bonus * c.usable * x[v])

    # P3: chunk order — chunk j requires chunk j-1
    by_lot_dst: dict[tuple[str, str, str, str], dict[int, int]] = {}
    for v, (_, c) in enumerate(active):
        lot_key = (c.chunk.lot.facility_id, c.chunk.lot.drug_code,
                   c.chunk.lot.batch_no, c.destination_id)
        by_lot_dst.setdefault(lot_key, {})[c.chunk.index] = v

    for _key, idx_to_var in by_lot_dst.items():
        for j, v_j in idx_to_var.items():
            if j > 0 and (j - 1) in idx_to_var:
                model.add(x[v_j] <= x[idx_to_var[j - 1]])

    # γ shared trip: bonus for consolidation
    if gamma > 0:
        by_trip: dict[tuple[str, str], list[int]] = {}
        for v, (_, c) in enumerate(active):
            trip_key = (c.chunk.lot.facility_id, c.destination_id)
            by_trip.setdefault(trip_key, []).append(v)

        for _tk, vs in by_trip.items():
            if len(vs) > 1:
                trip_var = model.new_bool_var(f"trip_{_tk}")
                for v in vs:
                    model.add(trip_var <= x[v]).only_enforce_if(x[v])
                model.add(trip_var >= 1).only_enforce_if([x[v] for v in vs[:2]])
                scaled_gamma = int(round(gamma * SCALE))
                obj_terms.append(scaled_gamma * trip_var)

    model.maximize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s

    status = solver.solve(model)

    status_name = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.MODEL_INVALID: "INVALID",
        cp_model.UNKNOWN: "UNKNOWN",
    }.get(status, "UNKNOWN")

    selected = []
    obj_val = 0.0
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        obj_val = solver.objective_value / SCALE
        for v, (ci, _) in enumerate(active):
            if solver.value(x[v]):
                selected.append(ci)

    ms = (time.perf_counter() - t0) * 1000

    return MILPResult(
        objective=obj_val,
        status=status_name,
        selected_indices=selected,
        time_ms=ms,
        meta={
            "n_vars": n,
            "n_constraints": len(model.proto.constraints),
            "wall_time_s": round(ms / 1000, 3),
        },
    )
