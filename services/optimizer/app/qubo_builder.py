"""QUBO matrix builder for v3 Hamiltonian (CLAUDE.md §6).

Pure functions: candidates + config in, Q matrix + offset out.
No I/O, no HTTP, no solver — brute-force enumeration in tests only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .candidates import Candidate


@dataclass
class QUBOConfig:
    p1: float = 2.0
    p2: float = 1.5
    p3: float = 1.0
    gamma: float | None = None  # None → 0.3 × min normalised trip cost


@dataclass
class QUBOResult:
    Q: dict[tuple[int, int], float]
    offset: float
    variables: list[int]  # indices into the original candidate list
    num_variables: int
    config_used: QUBOConfig
    norm_factor: float


MAX_VARIABLES = 150


def build_qubo(
    candidates: list[Candidate],
    ven_priority: dict[str, int],
    shortages: dict[tuple[str, str], int],
    config: QUBOConfig | None = None,
) -> QUBOResult:
    """Build upper-triangular QUBO dict from feasible selected candidates.

    Returns Q[(i,j)] for i <= j, a scalar offset, and the variable mapping.
    """
    cfg = config or QUBOConfig()

    active = [
        (ci, c)
        for ci, c in enumerate(candidates)
        if c.feasibility.feasible and c.selected
    ]
    if len(active) > MAX_VARIABLES:
        active = active[:MAX_VARIABLES]

    n = len(active)
    if n == 0:
        return QUBOResult(
            Q={}, offset=0.0, variables=[], num_variables=0,
            config_used=cfg, norm_factor=1.0,
        )

    cand_idx_to_var: dict[int, int] = {}
    var_to_cand: list[tuple[int, Candidate]] = []
    for v, (ci, c) in enumerate(active):
        cand_idx_to_var[ci] = v
        var_to_cand.append((ci, c))

    Q: dict[tuple[int, int], float] = {}
    offset = 0.0

    norm_factor = _norm_factor(active)

    # --- Reward term: −(s_i − c_i)/norm on diagonal ---
    for v, (_, c) in enumerate(var_to_cand):
        norm_reward = c.net_score / norm_factor
        _add(Q, v, v, -norm_reward)

    # --- P1 one-place: same chunk, different destination ---
    by_chunk: dict[str, list[int]] = {}
    for v, (_, c) in enumerate(var_to_cand):
        by_chunk.setdefault(c.chunk.chunk_id, []).append(v)

    for _cid, vs in by_chunk.items():
        for a in range(len(vs)):
            for b in range(a + 1, len(vs)):
                _add(Q, vs[a], vs[b], cfg.p1)

    # --- P2 shortage fill: per (destination, drug_code) ---
    by_dst_drug: dict[tuple[str, str], list[tuple[int, Candidate]]] = {}
    for v, (_, c) in enumerate(var_to_cand):
        by_dst_drug.setdefault((c.destination_id, c.drug_code), []).append((v, c))

    for (dst, drug), items in by_dst_drug.items():
        n_short = shortages.get((dst, drug), 0)
        if n_short <= 0:
            continue
        pi = ven_priority.get(drug, 1)

        for v, c in items:
            u = c.usable
            diag = cfg.p2 * pi * (u * u / (n_short * n_short) - 2 * u / n_short)
            _add(Q, v, v, diag)

        for a in range(len(items)):
            for b in range(a + 1, len(items)):
                va, ca = items[a]
                vb, cb = items[b]
                cross = cfg.p2 * 2 * pi * ca.usable * cb.usable / (n_short * n_short)
                _add(Q, va, vb, cross)

        offset += cfg.p2 * pi

    # --- P3 chunk order: per (lot, destination) ---
    by_lot_dst: dict[tuple[str, str, str, str], dict[int, int]] = {}
    for v, (_, c) in enumerate(var_to_cand):
        lot_key = (c.chunk.lot.facility_id, c.chunk.lot.drug_code,
                   c.chunk.lot.batch_no, c.destination_id)
        by_lot_dst.setdefault(lot_key, {})[c.chunk.index] = v

    for _key, idx_to_var in by_lot_dst.items():
        for j, v in idx_to_var.items():
            if j > 0:
                if (j - 1) in idx_to_var:
                    _add(Q, v, v, cfg.p3)
                    _add(Q, idx_to_var[j - 1], v, -cfg.p3)
                else:
                    _add(Q, v, v, cfg.p3)

    # --- γ shared trip: same (src, dst) ---
    gamma = _resolve_gamma(cfg, var_to_cand, norm_factor)

    if gamma > 0:
        by_trip: dict[tuple[str, str], list[int]] = {}
        for v, (_, c) in enumerate(var_to_cand):
            trip_key = (c.chunk.lot.facility_id, c.destination_id)
            by_trip.setdefault(trip_key, []).append(v)

        for _tk, vs in by_trip.items():
            for a in range(len(vs)):
                for b in range(a + 1, len(vs)):
                    _add(Q, vs[a], vs[b], -gamma)

    effective_cfg = QUBOConfig(p1=cfg.p1, p2=cfg.p2, p3=cfg.p3, gamma=gamma)

    return QUBOResult(
        Q=Q, offset=offset,
        variables=[ci for ci, _ in active],
        num_variables=n,
        config_used=effective_cfg,
        norm_factor=norm_factor,
    )


def energy(Q: dict[tuple[int, int], float], offset: float, x: dict[int, int]) -> float:
    """Compute H for a binary assignment x: {var_index: 0|1}."""
    total = offset
    for (i, j), w in Q.items():
        if i == j:
            total += w * x.get(i, 0)
        else:
            total += w * x.get(i, 0) * x.get(j, 0)
    return total


def brute_force_min(
    Q: dict[tuple[int, int], float], offset: float, n: int,
) -> tuple[dict[int, int], float]:
    """Enumerate all 2^n assignments, return (best_x, best_energy)."""
    best_e = float("inf")
    best_x: dict[int, int] = {}
    for bits in range(1 << n):
        x = {i: (bits >> i) & 1 for i in range(n)}
        e = energy(Q, offset, x)
        if e < best_e:
            best_e = e
            best_x = x
    return best_x, best_e


def term_breakdown(
    Q: dict[tuple[int, int], float],
    offset: float,
    x: dict[int, int],
    candidates: list[Candidate],
    variables: list[int],
    ven_priority: dict[str, int],
    shortages: dict[tuple[str, str], int],
    config: QUBOConfig,
    norm_factor: float,
) -> dict[str, Any]:
    """Decompose energy into per-term contributions. Sum == energy(Q, offset, x)."""
    var_cands = [(v, candidates[ci]) for v, ci in enumerate(variables)]
    n_vars = len(variables)

    reward_total = 0.0
    one_place_total = 0.0
    fill_total = 0.0
    chunk_order_total = 0.0
    shared_trip_total = 0.0

    # Reward
    for v, c in var_cands:
        norm_reward = c.net_score / norm_factor
        reward_total += (-norm_reward) * x.get(v, 0)

    # P1 one-place
    by_chunk: dict[str, list[int]] = {}
    for v, c in var_cands:
        by_chunk.setdefault(c.chunk.chunk_id, []).append(v)
    for _cid, vs in by_chunk.items():
        for a in range(len(vs)):
            for b in range(a + 1, len(vs)):
                one_place_total += config.p1 * x.get(vs[a], 0) * x.get(vs[b], 0)

    # P2 fill
    by_dst_drug: dict[tuple[str, str], list[tuple[int, Candidate]]] = {}
    for v, c in var_cands:
        by_dst_drug.setdefault((c.destination_id, c.drug_code), []).append((v, c))

    fill_offset = 0.0
    for (dst, drug), items in by_dst_drug.items():
        n_short = shortages.get((dst, drug), 0)
        if n_short <= 0:
            continue
        pi = ven_priority.get(drug, 1)
        fill_offset += config.p2 * pi
        for va, ca in items:
            u = ca.usable
            fill_total += config.p2 * pi * (u * u / (n_short * n_short) - 2 * u / n_short) * x.get(va, 0)
        for a in range(len(items)):
            for b in range(a + 1, len(items)):
                va, ca = items[a]
                vb, cb = items[b]
                fill_total += config.p2 * 2 * pi * ca.usable * cb.usable / (n_short * n_short) * x.get(va, 0) * x.get(vb, 0)
    fill_total += fill_offset

    # P3 chunk order
    by_lot_dst: dict[tuple[str, str, str, str], dict[int, int]] = {}
    for v, c in var_cands:
        lot_key = (c.chunk.lot.facility_id, c.chunk.lot.drug_code,
                   c.chunk.lot.batch_no, c.destination_id)
        by_lot_dst.setdefault(lot_key, {})[c.chunk.index] = v
    for _key, idx_to_var in by_lot_dst.items():
        for j, v_j in idx_to_var.items():
            if j > 0:
                chunk_order_total += config.p3 * x.get(v_j, 0)
                if (j - 1) in idx_to_var:
                    chunk_order_total += (-config.p3) * x.get(v_j, 0) * x.get(idx_to_var[j - 1], 0)

    # γ shared trip
    gamma = config.gamma if config.gamma is not None else 0.0
    if gamma > 0:
        by_trip: dict[tuple[str, str], list[int]] = {}
        for v, c in var_cands:
            trip_key = (c.chunk.lot.facility_id, c.destination_id)
            by_trip.setdefault(trip_key, []).append(v)
        for _tk, vs in by_trip.items():
            for a in range(len(vs)):
                for b in range(a + 1, len(vs)):
                    shared_trip_total += (-gamma) * x.get(vs[a], 0) * x.get(vs[b], 0)

    total = reward_total + one_place_total + fill_total + chunk_order_total + shared_trip_total

    return {
        "reward": reward_total,
        "one_place_penalty": one_place_total,
        "fill_penalty": fill_total,
        "chunk_order_penalty": chunk_order_total,
        "shared_trip_bonus": shared_trip_total,
        "total": total,
    }


# ── internal helpers ──


def _add(Q: dict[tuple[int, int], float], i: int, j: int, val: float) -> None:
    """Add val to Q[(min(i,j), max(i,j))] (upper-triangular)."""
    key = (min(i, j), max(i, j))
    Q[key] = Q.get(key, 0.0) + val


def _norm_factor(active: list[tuple[int, Candidate]]) -> float:
    """Normalise rewards so max positive = 1. Fallback: max |net| or 1."""
    positive = [c.net_score for _, c in active if c.net_score > 0]
    if positive:
        return max(positive)
    all_abs = [abs(c.net_score) for _, c in active if c.net_score != 0]
    return max(all_abs) if all_abs else 1.0


def _resolve_gamma(
    cfg: QUBOConfig,
    var_to_cand: list[tuple[int, Candidate]],
    norm_factor: float,
) -> float:
    if cfg.gamma is not None:
        return cfg.gamma
    trip_costs = [c.trip_cost / norm_factor for _, c in var_to_cand if c.trip_cost > 0]
    return 0.3 * min(trip_costs) if trip_costs else 0.0
