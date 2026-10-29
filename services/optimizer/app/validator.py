"""FEFO re-simulation validator with repair for QUBO solutions.

Pure functions operating on snapshot copies — never mutates real DB.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .candidates import Candidate
from .feasibility import check_feasibility, BUFFER_DAYS
from .positions import compute_all_positions
from .snapshot import Snapshot, Lot, Position


@dataclass
class Violation:
    order_index: int
    rule: str
    detail: str


@dataclass
class ValidatedOrder:
    candidate_index: int
    src_facility_id: str
    dst_facility_id: str
    drug_code: str
    batch_no: str
    qty: int
    usable: int
    trimmed: bool = False
    dropped: bool = False


@dataclass
class ValidationResult:
    orders: list[ValidatedOrder]
    violations: list[Violation]
    trimmed_count: int
    dropped_count: int


def apply_plan(
    snap: Snapshot,
    selected: list[tuple[int, Candidate]],
) -> ValidationResult:
    """Validate a QUBO solution by re-simulating FEFO on a snapshot copy.

    selected: list of (candidate_index, Candidate) for variables set to 1.
    Returns validated orders with any trims or drops.
    """
    snap_copy = _deep_copy_snapshot(snap)

    orders: list[ValidatedOrder] = []
    violations: list[Violation] = []
    assigned_chunks: set[str] = set()
    trimmed_count = 0
    dropped_count = 0

    sorted_sel = sorted(selected, key=lambda t: -t[1].usable)

    for idx, (ci, cand) in enumerate(sorted_sel):
        order = ValidatedOrder(
            candidate_index=ci,
            src_facility_id=cand.chunk.lot.facility_id,
            dst_facility_id=cand.destination_id,
            drug_code=cand.drug_code,
            batch_no=cand.chunk.lot.batch_no,
            qty=cand.chunk.qty,
            usable=cand.usable,
        )

        # Double-ship check
        chunk_id = cand.chunk.chunk_id
        if chunk_id in assigned_chunks:
            violations.append(Violation(idx, "double_ship", f"Chunk {chunk_id} already assigned"))
            order.dropped = True
            dropped_count += 1
            orders.append(order)
            continue
        assigned_chunks.add(chunk_id)

        drug = snap_copy.drugs.get(cand.drug_code)
        if not drug:
            violations.append(Violation(idx, "unknown_drug", f"Drug {cand.drug_code} not in snapshot"))
            order.dropped = True
            dropped_count += 1
            orders.append(order)
            continue

        # Controlled drug check
        if drug.controlled:
            violations.append(Violation(idx, "controlled", f"{cand.drug_code} is controlled"))
            order.dropped = True
            dropped_count += 1
            orders.append(order)
            continue

        # Cold chain check
        route = snap_copy.routes.get((order.src_facility_id, order.dst_facility_id))
        if drug.cold_chain:
            dst_fac = snap_copy.facilities.get(order.dst_facility_id)
            cold_route = route.cold_chain if route else False
            cold_vehicle = any(v.cold_chain for v in snap_copy.vehicles)
            cold_storage = dst_fac.cold_storage if dst_fac else False
            if not (cold_route and cold_vehicle and cold_storage):
                violations.append(Violation(idx, "cold_chain", "Cold chain not met"))
                order.dropped = True
                dropped_count += 1
                orders.append(order)
                continue

        # Source lot availability
        src_key = (order.src_facility_id, order.drug_code)
        src_lots = snap_copy.lots_by_fd.get(src_key, [])
        src_lot = None
        for lot in src_lots:
            if lot.batch_no == order.batch_no:
                src_lot = lot
                break

        if src_lot is None or src_lot.qty < order.qty:
            available = src_lot.qty if src_lot else 0
            violations.append(Violation(
                idx, "negative_stock",
                f"Source has {available} but needs {order.qty}",
            ))
            if available > 0:
                order.qty = available
                order.trimmed = True
                trimmed_count += 1
            else:
                order.dropped = True
                dropped_count += 1
                orders.append(order)
                continue

        # Reserve check: after transfer, source must keep reserve
        positions = compute_all_positions(snap_copy)
        src_pos = positions.get(src_key)
        if src_pos:
            post_transfer_total = sum(l.qty for l in snap_copy.lots_by_fd.get(src_key, [])) - order.qty
            if post_transfer_total < src_pos.reserve:
                violations.append(Violation(
                    idx, "reserve_breach",
                    f"Post-transfer stock {post_transfer_total} < reserve {src_pos.reserve}",
                ))
                safe_qty = max(0, sum(l.qty for l in snap_copy.lots_by_fd.get(src_key, [])) - src_pos.reserve)
                if safe_qty > 0:
                    order.qty = min(order.qty, safe_qty)
                    order.trimmed = True
                    trimmed_count += 1
                else:
                    order.dropped = True
                    dropped_count += 1
                    orders.append(order)
                    continue

        # Re-compute usable at destination
        if route:
            transit_days = route.transit_days
            remaining_shelf = (src_lot.expiry - snap_copy.today).days - transit_days - BUFFER_DAYS
            if remaining_shelf <= 0:
                violations.append(Violation(idx, "expired_on_arrival", "Would expire in transit"))
                order.dropped = True
                dropped_count += 1
                orders.append(order)
                continue

            dst_pos = snap_copy.positions.get((order.dst_facility_id, order.drug_code))
            dst_rate = dst_pos.rate if dst_pos else 0.0
            dst_earlier = sum(
                l.qty for l in snap_copy.lots_by_fd.get((order.dst_facility_id, order.drug_code), [])
                if l.expiry < src_lot.expiry
            )
            realised_usable = min(order.qty, max(0, int(dst_rate * remaining_shelf - dst_earlier)))

            if realised_usable <= 0:
                violations.append(Violation(idx, "zero_usable", "Realised usable is 0"))
                order.dropped = True
                dropped_count += 1
                orders.append(order)
                continue

            if realised_usable < order.usable:
                order.usable = realised_usable
                order.qty = min(order.qty, realised_usable)
                order.trimmed = True
                trimmed_count += 1

        # Apply transfer to snapshot copy
        _apply_transfer(snap_copy, order)
        orders.append(order)

    return ValidationResult(
        orders=orders,
        violations=violations,
        trimmed_count=trimmed_count,
        dropped_count=dropped_count,
    )


def repair(
    Q: dict[tuple[int, int], float],
    offset: float,
    violations: list[Violation],
    candidates: list[Candidate],
    selected_indices: list[int],
    *,
    max_attempts: int = 3,
) -> list[int]:
    """Drop lowest-reward violating orders. Return cleaned selected_indices."""
    from .qubo_builder import energy

    cleaned = list(selected_indices)

    for _attempt in range(max_attempts):
        if not violations:
            break

        violating = {v.order_index for v in violations}
        worst_idx = None
        worst_reward = float("inf")

        for oi in violating:
            if oi < len(candidates):
                r = candidates[oi].net_score
                if r < worst_reward:
                    worst_reward = r
                    worst_idx = oi

        if worst_idx is not None and worst_idx in cleaned:
            cleaned.remove(worst_idx)

        violations = [v for v in violations if v.order_index != worst_idx]

    return cleaned


def _deep_copy_snapshot(snap: Snapshot) -> Snapshot:
    new_snap = Snapshot(today=snap.today)
    new_snap.facilities = dict(snap.facilities)
    new_snap.drugs = dict(snap.drugs)
    new_snap.routes = dict(snap.routes)
    new_snap.vehicles = list(snap.vehicles)
    new_snap.lots = list(snap.lots)
    new_snap.lots_by_fd = {k: list(v) for k, v in snap.lots_by_fd.items()}
    new_snap.positions = {k: copy.copy(v) for k, v in snap.positions.items()}
    new_snap.policies = dict(snap.policies)
    return new_snap


def _apply_transfer(snap: Snapshot, order: ValidatedOrder) -> None:
    src_key = (order.src_facility_id, order.drug_code)
    src_lots = snap.lots_by_fd.get(src_key, [])

    new_src_lots = []
    for lot in src_lots:
        if lot.batch_no == order.batch_no:
            remaining = lot.qty - order.qty
            if remaining > 0:
                new_src_lots.append(Lot(
                    facility_id=lot.facility_id, drug_code=lot.drug_code,
                    batch_no=lot.batch_no, expiry=lot.expiry, qty=remaining,
                ))
        else:
            new_src_lots.append(lot)
    snap.lots_by_fd[src_key] = new_src_lots

    dst_key = (order.dst_facility_id, order.drug_code)
    dst_lots = snap.lots_by_fd.get(dst_key, [])

    existing = None
    for lot in dst_lots:
        if lot.batch_no == order.batch_no:
            existing = lot
            break

    if existing:
        new_dst_lots = []
        for lot in dst_lots:
            if lot.batch_no == order.batch_no:
                new_dst_lots.append(Lot(
                    facility_id=order.dst_facility_id, drug_code=lot.drug_code,
                    batch_no=lot.batch_no, expiry=lot.expiry,
                    qty=lot.qty + order.qty,
                ))
            else:
                new_dst_lots.append(lot)
        snap.lots_by_fd[dst_key] = new_dst_lots
    else:
        src_lot = None
        for lot in snap.lots:
            if lot.batch_no == order.batch_no and lot.drug_code == order.drug_code:
                src_lot = lot
                break
        expiry = src_lot.expiry if src_lot else snap.today
        new_lot = Lot(
            facility_id=order.dst_facility_id, drug_code=order.drug_code,
            batch_no=order.batch_no, expiry=expiry, qty=order.qty,
        )
        snap.lots_by_fd.setdefault(dst_key, []).append(new_lot)
