"""Regret ledger: per-order ΔH analysis of alternatives.

For each order in the plan, evaluate what would happen if its chunk went to
each alternative destination (or to nowhere), using both the best sample and
alternative top-k samples from the solver.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .candidates import Candidate
from .qubo_builder import QUBOResult, energy
from .solvers.port import SolveResult


REASON_CODES = {
    "LOWER_USABLE": "alternative destination receives fewer usable units",
    "HIGHER_COST": "alternative has higher trip cost",
    "LOWER_VEN": "alternative drug has lower VEN priority",
    "FAILED_RULE_F1": "failed feasibility rule F1 (identity)",
    "FAILED_RULE_F2": "failed feasibility rule F2 (no route)",
    "FAILED_RULE_F3": "failed feasibility rule F3 (cold chain)",
    "FAILED_RULE_F4": "failed feasibility rule F4 (usable/shelf life)",
    "FAILED_RULE_F5": "failed feasibility rule F5 (reserve)",
    "FAILED_RULE_F6": "failed feasibility rule F6 (controlled)",
    "WORSE_FILL": "alternative worsens shortage fill ratio",
}


@dataclass
class RegretEntry:
    alternative_dst: str | None
    delta_h: float
    reason_code: str
    reason_text: str
    source: str  # "best_sample" or "sample_k"

    def to_dict(self) -> dict[str, Any]:
        return {
            "alternative_dst": self.alternative_dst,
            "delta_h": round(self.delta_h, 6),
            "reason_code": self.reason_code,
            "reason_text": self.reason_text,
            "source": self.source,
        }


@dataclass
class OrderRegret:
    order_id: str
    var_index: int
    current_dst: str
    current_energy: float
    entries: list[RegretEntry]

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "var_index": self.var_index,
            "current_dst": self.current_dst,
            "current_energy": round(self.current_energy, 6),
            "top_alternatives": [e.to_dict() for e in self.entries[:5]],
        }


def _classify_reason(
    cand: Candidate,
    current_cand: Candidate,
    ven_priority: dict[str, int],
) -> tuple[str, str]:
    """Classify why an alternative lost: return (reason_code, reason_text)."""
    if not cand.feasibility.feasible:
        for fr in cand.feasibility.failed_rules:
            code = f"FAILED_RULE_{fr.rule}"
            return code, f"rule {fr.rule} failed: {fr.detail}"
        return "FAILED_RULE_F1", "infeasible (unknown rule)"

    if cand.usable < current_cand.usable:
        return (
            "LOWER_USABLE",
            f"usable {cand.usable} vs {current_cand.usable} at {current_cand.destination_id}",
        )

    if cand.trip_cost > current_cand.trip_cost:
        return (
            "HIGHER_COST",
            f"trip cost ₹{cand.trip_cost:.0f} vs ₹{current_cand.trip_cost:.0f}",
        )

    cur_pi = ven_priority.get(current_cand.drug_code, 1)
    alt_pi = ven_priority.get(cand.drug_code, 1)
    if alt_pi < cur_pi:
        return "LOWER_VEN", f"VEN priority {alt_pi} vs {cur_pi}"

    if cand.net_score < current_cand.net_score:
        return (
            "WORSE_FILL",
            f"net score {cand.net_score:.2f} vs {current_cand.net_score:.2f}",
        )

    return "WORSE_FILL", f"ΔH positive (net score {cand.net_score:.2f} vs {current_cand.net_score:.2f})"


def compute_regret(
    order_ids: list[str],
    candidates: list[Candidate],
    qubo_result: QUBOResult,
    solve_result: SolveResult,
    ven_priority: dict[str, int],
) -> list[OrderRegret]:
    """Compute regret ledger for each selected order.

    For each order's QUBO variable:
    1. Flip it to 0 (send nowhere) → ΔH
    2. Flip it to 0 and each alternative destination's variable to 1 → ΔH
    3. Check alternative top-k samples for better assignments
    """
    if not solve_result.samples or not qubo_result.variables:
        return []

    best = solve_result.samples[0]
    Q = qubo_result.Q
    offset = qubo_result.offset
    base_energy = energy(Q, offset, best.x)

    var_to_cand_idx = {v: ci for v, ci in enumerate(qubo_result.variables)}
    cand_idx_to_var = {ci: v for v, ci in var_to_cand_idx.items()}

    selected_vars = {v for v, val in best.x.items() if val == 1}

    by_chunk: dict[str, list[int]] = {}
    for v, ci in var_to_cand_idx.items():
        c = candidates[ci]
        by_chunk.setdefault(c.chunk.chunk_id, []).append(v)

    results: list[OrderRegret] = []

    for order_idx, order_id in enumerate(order_ids):
        var_idx = None
        current_cand = None
        for v in selected_vars:
            ci = var_to_cand_idx.get(v)
            if ci is not None and order_idx < len(order_ids):
                c = candidates[ci]
                if v in selected_vars:
                    if len(results) == order_idx:
                        var_idx = v
                        current_cand = c
                        break

        if var_idx is None or current_cand is None:
            continue

        entries: list[RegretEntry] = []

        # Alternative 1: send nowhere (flip var_idx to 0)
        x_nowhere = dict(best.x)
        x_nowhere[var_idx] = 0
        e_nowhere = energy(Q, offset, x_nowhere)
        dh_nowhere = e_nowhere - base_energy
        entries.append(RegretEntry(
            alternative_dst=None,
            delta_h=dh_nowhere,
            reason_code="LOWER_USABLE",
            reason_text=f"not sending: ΔH={dh_nowhere:+.4f}, losing {current_cand.usable} usable units",
            source="best_sample",
        ))

        # Alternative 2: each alternative destination for the same chunk
        chunk_id = current_cand.chunk.chunk_id
        sibling_vars = by_chunk.get(chunk_id, [])
        for alt_v in sibling_vars:
            if alt_v == var_idx:
                continue
            alt_ci = var_to_cand_idx[alt_v]
            alt_cand = candidates[alt_ci]

            x_alt = dict(best.x)
            x_alt[var_idx] = 0
            x_alt[alt_v] = 1
            e_alt = energy(Q, offset, x_alt)
            dh_alt = e_alt - base_energy

            reason_code, reason_text = _classify_reason(
                alt_cand, current_cand, ven_priority,
            )
            entries.append(RegretEntry(
                alternative_dst=alt_cand.destination_id,
                delta_h=dh_alt,
                reason_code=reason_code,
                reason_text=f"→{alt_cand.destination_id}: ΔH={dh_alt:+.4f}, {reason_text}",
                source="best_sample",
            ))

        # Alternative 3: best alternative from other top-k samples
        for k_idx, sample in enumerate(solve_result.samples[1:], start=1):
            alt_val = sample.x.get(var_idx, 0)
            if alt_val == 1:
                continue
            for alt_v in sibling_vars:
                if sample.x.get(alt_v, 0) == 1 and alt_v != var_idx:
                    alt_ci = var_to_cand_idx[alt_v]
                    alt_cand = candidates[alt_ci]
                    dh_sample = sample.energy - base_energy
                    reason_code, reason_text = _classify_reason(
                        alt_cand, current_cand, ven_priority,
                    )
                    entries.append(RegretEntry(
                        alternative_dst=alt_cand.destination_id,
                        delta_h=dh_sample,
                        reason_code=reason_code,
                        reason_text=f"sample#{k_idx}→{alt_cand.destination_id}: ΔH={dh_sample:+.4f}, {reason_text}",
                        source=f"sample_{k_idx}",
                    ))
                    break

        entries.sort(key=lambda e: e.delta_h)

        results.append(OrderRegret(
            order_id=order_id,
            var_index=var_idx,
            current_dst=current_cand.destination_id,
            current_energy=base_energy,
            entries=entries[:5],
        ))

    return results


def compute_regret_from_vars(
    selected_var_to_order_id: dict[int, str],
    candidates: list[Candidate],
    qubo_result: QUBOResult,
    solve_result: SolveResult,
    ven_priority: dict[str, int],
) -> list[OrderRegret]:
    """Compute regret using explicit var→order_id mapping (used by router)."""
    if not solve_result.samples or not qubo_result.variables:
        return []

    best = solve_result.samples[0]
    Q = qubo_result.Q
    offset = qubo_result.offset
    base_energy = energy(Q, offset, best.x)

    var_to_cand_idx = {v: ci for v, ci in enumerate(qubo_result.variables)}

    by_chunk: dict[str, list[int]] = {}
    for v, ci in var_to_cand_idx.items():
        c = candidates[ci]
        by_chunk.setdefault(c.chunk.chunk_id, []).append(v)

    results: list[OrderRegret] = []

    for var_idx, order_id in selected_var_to_order_id.items():
        ci = var_to_cand_idx.get(var_idx)
        if ci is None:
            continue
        current_cand = candidates[ci]

        entries: list[RegretEntry] = []

        x_nowhere = dict(best.x)
        x_nowhere[var_idx] = 0
        e_nowhere = energy(Q, offset, x_nowhere)
        dh_nowhere = e_nowhere - base_energy
        entries.append(RegretEntry(
            alternative_dst=None,
            delta_h=dh_nowhere,
            reason_code="LOWER_USABLE",
            reason_text=f"not sending: ΔH={dh_nowhere:+.4f}, losing {current_cand.usable} usable units",
            source="best_sample",
        ))

        chunk_id = current_cand.chunk.chunk_id
        sibling_vars = by_chunk.get(chunk_id, [])
        for alt_v in sibling_vars:
            if alt_v == var_idx:
                continue
            alt_ci = var_to_cand_idx[alt_v]
            alt_cand = candidates[alt_ci]

            x_alt = dict(best.x)
            x_alt[var_idx] = 0
            x_alt[alt_v] = 1
            e_alt = energy(Q, offset, x_alt)
            dh_alt = e_alt - base_energy

            reason_code, reason_text = _classify_reason(
                alt_cand, current_cand, ven_priority,
            )
            entries.append(RegretEntry(
                alternative_dst=alt_cand.destination_id,
                delta_h=dh_alt,
                reason_code=reason_code,
                reason_text=f"→{alt_cand.destination_id}: ΔH={dh_alt:+.4f}, {reason_text}",
                source="best_sample",
            ))

        for k_idx, sample in enumerate(solve_result.samples[1:], start=1):
            if sample.x.get(var_idx, 0) == 1:
                continue
            for alt_v in sibling_vars:
                if sample.x.get(alt_v, 0) == 1 and alt_v != var_idx:
                    alt_ci = var_to_cand_idx[alt_v]
                    alt_cand = candidates[alt_ci]
                    dh_sample = sample.energy - base_energy
                    reason_code, reason_text = _classify_reason(
                        alt_cand, current_cand, ven_priority,
                    )
                    entries.append(RegretEntry(
                        alternative_dst=alt_cand.destination_id,
                        delta_h=dh_sample,
                        reason_code=reason_code,
                        reason_text=f"sample#{k_idx}→{alt_cand.destination_id}: ΔH={dh_sample:+.4f}, {reason_text}",
                        source=f"sample_{k_idx}",
                    ))
                    break

        entries.sort(key=lambda e: e.delta_h)

        results.append(OrderRegret(
            order_id=order_id,
            var_index=var_idx,
            current_dst=current_cand.destination_id,
            current_energy=base_energy,
            entries=entries[:5],
        ))

    return results
