"""Why-not explainer: for unserved shortages, explain every candidate that lost."""
from __future__ import annotations

from typing import Any

from .baselines import TransferOrder
from .candidates import Candidate
from .snapshot import Snapshot


def compute_whynot(
    facility_id: str,
    drug_code: str,
    snap: Snapshot,
    candidates: list[Candidate],
    orders: list[TransferOrder],
) -> dict[str, Any]:
    """Explain residual shortage at (facility, drug) after the plan.

    Returns:
      - residual_shortage: units still short after transfers
      - supplied: units transferred to this facility+drug
      - candidates: every source lot considered, with failed rules or net_score
    """
    pos = snap.positions.get((facility_id, drug_code))
    shortage_before = pos.shortage if pos else 0

    supplied = sum(
        o.usable for o in orders
        if o.dst_facility_id == facility_id and o.drug_code == drug_code
    )
    residual = max(0, shortage_before - supplied)

    candidate_explanations: list[dict[str, Any]] = []

    for c in candidates:
        if c.destination_id != facility_id or c.drug_code != drug_code:
            continue

        src_lot = c.chunk.lot
        entry: dict[str, Any] = {
            "src_facility": src_lot.facility_id,
            "batch_no": src_lot.batch_no,
            "chunk_id": c.chunk.chunk_id,
            "chunk_qty": c.chunk.qty,
            "usable": c.usable,
            "net_score": round(c.net_score, 4),
            "selected": c.selected,
            "feasible": c.feasibility.feasible,
        }

        if not c.feasibility.feasible:
            entry["failed_rules"] = [
                {"rule": fr.rule, "detail": fr.detail}
                for fr in c.feasibility.failed_rules
            ]
            entry["reason"] = "; ".join(
                f"{fr.rule}: {fr.detail}" for fr in c.feasibility.failed_rules
            )
        elif not c.selected:
            entry["reason"] = f"not in top-k destinations (net_score={c.net_score:.2f})"
        else:
            was_used = any(
                o.batch_no == src_lot.batch_no
                and o.src_facility_id == src_lot.facility_id
                and o.dst_facility_id == facility_id
                and o.drug_code == drug_code
                for o in orders
            )
            if was_used:
                entry["reason"] = "selected and used in plan"
                entry["in_plan"] = True
            else:
                entry["reason"] = f"selected but dropped by validator or displaced by higher-scoring candidate"

        candidate_explanations.append(entry)

    candidate_explanations.sort(key=lambda e: (-e.get("feasible", False), -e.get("net_score", 0)))

    return {
        "facility_id": facility_id,
        "drug_code": drug_code,
        "shortage_before": shortage_before,
        "supplied": supplied,
        "residual_shortage": residual,
        "candidates_considered": len(candidate_explanations),
        "candidates": candidate_explanations,
    }
