"""Compute FEFO positions for all (facility, drug) pairs in a snapshot."""
from __future__ import annotations

from medbal_common.fefo import compute_position, PositionResult

from .snapshot import Snapshot, Position


def compute_all_positions(snap: Snapshot) -> dict[tuple[str, str], PositionResult]:
    """Recompute positions from lots using medbal_common.fefo."""
    results: dict[tuple[str, str], PositionResult] = {}
    for (fac_id, drug_code), lots in snap.lots_by_fd.items():
        pos = snap.positions.get((fac_id, drug_code))
        policy = snap.policies.get((fac_id, drug_code))
        rate = pos.rate if pos else 0.0
        target = policy.target_days if policy else (pos.target_days if pos else 21)
        min_reserve = policy.min_reserve_days if policy else 7
        lead_time = policy.lead_time_days if policy else 3

        lot_dicts = [
            {"batch_no": l.batch_no, "expiry": l.expiry, "qty": l.qty}
            for l in lots
        ]
        result = compute_position(
            facility_id=fac_id,
            drug_code=drug_code,
            lots=lot_dicts,
            rate=rate,
            today=snap.today,
            min_reserve_days=min_reserve,
            target_days=target,
            lead_time_days=lead_time,
        )
        results[(fac_id, drug_code)] = result
    return results


def dst_stock_expiring_before(snap: Snapshot, dst_id: str, drug_code: str, before_date) -> int:
    """Sum of destination stock (same drug) with expiry strictly before `before_date`."""
    lots = snap.lots_by_fd.get((dst_id, drug_code), [])
    return sum(l.qty for l in lots if l.expiry < before_date)
