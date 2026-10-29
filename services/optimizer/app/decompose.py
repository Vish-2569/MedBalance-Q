"""Zone-decomposed QUBO solving.

1. Zone facilities via Max-Cut.
2. Build per-zone QUBO from candidates within each zone.
3. Build boundary QUBO for cross-zone candidates using residual shortages.
4. Merge, validate.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from medbal_common.logging import get_logger

from .baselines import TransferOrder
from .candidates import Candidate, generate_candidates
from .metrics import compute_metrics
from .milp import MILPResult
from .positions import compute_all_positions
from .qubo_builder import build_qubo, QUBOConfig, energy
from .snapshot import Snapshot
from .solvers import solve_chain
from .solvers.greedy_descent import GreedyDescent
from .validator import apply_plan, ValidationResult
from .zoning import zone_facilities, ZoneResult

log = get_logger("optimizer.decompose")


@dataclass
class DecomposeResult:
    orders: list[TransferOrder]
    zone_result: ZoneResult
    zone_solve_times: dict[int, float]
    boundary_solve_time: float
    total_time_ms: float
    violations: int
    meta: dict[str, Any] = field(default_factory=dict)


def decomposed_solve(
    snap: Snapshot,
    candidates: list[Candidate],
    *,
    config: QUBOConfig | None = None,
    mode: str = "live",
    taluk_map: dict[str, str] | None = None,
    depth: int = 1,
    shots: int = 1024,
) -> DecomposeResult:
    """Solve via zone decomposition: per-zone QUBO + boundary QUBO."""
    t0 = time.perf_counter()
    cfg = config or QUBOConfig()

    # Step 1: zone
    zr = zone_facilities(snap, mode=mode, taluk_map=taluk_map, depth=depth, shots=shots)

    ven_priority = {code: drug.ven_priority for code, drug in snap.drugs.items()}
    shortages = {
        (fac_id, dc): pos.shortage
        for (fac_id, dc), pos in snap.positions.items()
        if pos.shortage > 0
    }

    # Step 2: per-zone QUBO
    all_selected: list[tuple[int, Candidate]] = []
    zone_times: dict[int, float] = {}

    for zone_id, fac_ids in zr.zone_facilities.items():
        fac_set = set(fac_ids)
        zone_cands = [
            c for c in candidates
            if c.chunk.lot.facility_id in fac_set and c.destination_id in fac_set
        ]

        if not zone_cands:
            zone_times[zone_id] = 0.0
            continue

        zt0 = time.perf_counter()
        qubo = build_qubo(zone_cands, ven_priority, shortages, cfg)

        if qubo.num_variables == 0:
            zone_times[zone_id] = (time.perf_counter() - zt0) * 1000
            continue

        sr = solve_chain(qubo.Q, qubo.offset, qubo.num_variables, top_k=5)
        zone_times[zone_id] = (time.perf_counter() - zt0) * 1000

        if sr.samples:
            best = sr.samples[0]
            for v, val in best.x.items():
                if val == 1 and v < len(qubo.variables):
                    ci = qubo.variables[v]
                    orig_idx = candidates.index(zone_cands[ci]) if ci < len(zone_cands) else -1
                    if orig_idx >= 0:
                        all_selected.append((orig_idx, candidates[orig_idx]))

    # Step 3: boundary QUBO (cross-zone candidates with residual shortages)
    bt0 = time.perf_counter()

    filled: dict[tuple[str, str], int] = {}
    for _, c in all_selected:
        key = (c.destination_id, c.drug_code)
        filled[key] = filled.get(key, 0) + c.usable

    residual = {}
    for key, n in shortages.items():
        remaining = n - filled.get(key, 0)
        if remaining > 0:
            residual[key] = remaining

    zone_map = zr.zones
    cross_cands = [
        c for c in candidates
        if zone_map.get(c.chunk.lot.facility_id, 0) != zone_map.get(c.destination_id, 0)
        and c.feasibility.feasible and c.selected
    ]

    if cross_cands and residual:
        bqubo = build_qubo(cross_cands, ven_priority, residual, cfg)
        if bqubo.num_variables > 0:
            bsr = solve_chain(bqubo.Q, bqubo.offset, bqubo.num_variables, top_k=3)
            if bsr.samples:
                best_b = bsr.samples[0]
                for v, val in best_b.x.items():
                    if val == 1 and v < len(bqubo.variables):
                        ci = bqubo.variables[v]
                        if ci < len(cross_cands):
                            orig_idx = candidates.index(cross_cands[ci])
                            all_selected.append((orig_idx, candidates[orig_idx]))

    boundary_time = (time.perf_counter() - bt0) * 1000

    # Step 4: validate + convert
    val_result = apply_plan(snap, all_selected)
    orders: list[TransferOrder] = []
    for vo in val_result.orders:
        if vo.dropped:
            continue
        drug = snap.drugs.get(vo.drug_code)
        orders.append(TransferOrder(
            id=f"ORD-Z-{len(orders)+1:03d}",
            src_facility_id=vo.src_facility_id,
            dst_facility_id=vo.dst_facility_id,
            drug_code=vo.drug_code,
            drug_name=drug.name if drug else vo.drug_code,
            batch_no=vo.batch_no,
            qty=vo.qty,
            usable=vo.usable,
            score=0.0,
            temperature_req="cold_chain" if (drug and drug.cold_chain) else "ambient",
        ))

    total_ms = (time.perf_counter() - t0) * 1000

    return DecomposeResult(
        orders=orders,
        zone_result=zr,
        zone_solve_times=zone_times,
        boundary_solve_time=boundary_time,
        total_time_ms=total_ms,
        violations=len(val_result.violations),
        meta={
            "zones": len(zr.zone_facilities),
            "zone_candidates": {z: sum(1 for c in candidates
                                       if c.chunk.lot.facility_id in set(facs)
                                       and c.destination_id in set(facs))
                                for z, facs in zr.zone_facilities.items()},
            "cross_candidates": len(cross_cands),
            "residual_shortages": len(residual),
        },
    )
