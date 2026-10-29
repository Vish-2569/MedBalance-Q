"""Greedy baselines for comparison with QUBO solver."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from medbal_common.fefo import compute_position, PositionResult

from .candidates import Candidate, compute_usable, split_chunks, Chunk
from .feasibility import check_feasibility, check_f1_f3_only, BUFFER_DAYS
from .positions import dst_stock_expiring_before, compute_all_positions
from .snapshot import Snapshot


@dataclass
class TransferOrder:
    id: str
    src_facility_id: str
    dst_facility_id: str
    drug_code: str
    drug_name: str
    batch_no: str
    qty: int
    usable: int
    score: float
    temperature_req: str
    status: str = "proposed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "src_facility_id": self.src_facility_id,
            "dst_facility_id": self.dst_facility_id,
            "drug_code": self.drug_code,
            "drug_name": self.drug_name,
            "batch_no": self.batch_no,
            "qty": self.qty,
            "usable": self.usable,
            "score": round(self.score, 4),
            "status": self.status,
            "temperature_req": self.temperature_req,
        }


def greedy_phone_call(snap: Snapshot) -> list[TransferOrder]:
    """Greedy: shortages by VEN×size, nearest at-risk source, F1-F3 only.

    Models current practice where pharmacists phone nearby facilities.
    May move waste (doesn't check usable).
    """
    src_positions = compute_all_positions(snap)
    shortages = _sorted_shortages(snap)
    orders: list[TransferOrder] = []
    used: dict[tuple[str, str, str], int] = {}

    for dst_id, drug_code, shortage_qty in shortages:
        drug = snap.drugs.get(drug_code)
        if not drug:
            continue

        sources = _nearest_sources_with_atrisk(snap, src_positions, drug_code, dst_id)
        remaining = shortage_qty

        for src_id, distance, src_pos in sources:
            if remaining <= 0:
                break

            feas = check_f1_f3_only(src_id, dst_id, drug_code, snap)
            if not feas.feasible:
                continue

            for lot_pos in src_pos.lots:
                if remaining <= 0:
                    break
                if lot_pos.at_risk <= 0:
                    continue

                used_key = (src_id, drug_code, lot_pos.batch_no)
                already_used = used.get(used_key, 0)
                available = lot_pos.at_risk - already_used
                if available <= 0:
                    continue

                qty = min(available, remaining)
                used[used_key] = already_used + qty
                remaining -= qty

                orders.append(TransferOrder(
                    id=f"ORD-PC-{len(orders)+1:03d}",
                    src_facility_id=src_id,
                    dst_facility_id=dst_id,
                    drug_code=drug_code,
                    drug_name=drug.name,
                    batch_no=lot_pos.batch_no,
                    qty=qty,
                    usable=qty,
                    score=0.5,
                    temperature_req="cold_chain" if drug.cold_chain else "ambient",
                ))

    return orders


def greedy_f4(snap: Snapshot) -> list[TransferOrder]:
    """Greedy with full F1-F6 and usable quantities.

    Respects all feasibility rules. Won't move stock that can't be used.
    """
    src_positions = compute_all_positions(snap)
    shortages = _sorted_shortages(snap)
    orders: list[TransferOrder] = []
    used: dict[tuple[str, str, str], int] = {}
    dst_allocated: dict[tuple[str, str], int] = {}

    for dst_id, drug_code, shortage_qty in shortages:
        drug = snap.drugs.get(drug_code)
        if not drug:
            continue

        sources = _nearest_sources_with_atrisk(snap, src_positions, drug_code, dst_id)
        remaining = shortage_qty - dst_allocated.get((dst_id, drug_code), 0)

        for src_id, distance, src_pos in sources:
            if remaining <= 0:
                break

            route = snap.routes.get((src_id, dst_id))
            if not route:
                continue

            for lot_pos in src_pos.lots:
                if remaining <= 0:
                    break
                if lot_pos.transferable <= 0:
                    continue

                lot = _find_lot(snap, src_id, drug_code, lot_pos.batch_no)
                if not lot:
                    continue

                used_key = (src_id, drug_code, lot_pos.batch_no)
                already_used = used.get(used_key, 0)
                available = lot_pos.transferable - already_used
                if available <= 0:
                    continue

                dst_earlier = dst_stock_expiring_before(
                    snap, dst_id, drug_code, lot.expiry
                )
                prev_alloc = dst_allocated.get((dst_id, drug_code), 0)

                dst_pos = snap.positions.get((dst_id, drug_code))
                dst_rate = dst_pos.rate if dst_pos else 0.0

                usable = compute_usable(
                    available, lot.expiry, dst_rate,
                    snap.today, route.transit_days, dst_earlier + prev_alloc,
                )

                feas = check_feasibility(
                    src_facility_id=src_id,
                    dst_facility_id=dst_id,
                    drug_code=drug_code,
                    lot_expiry=lot.expiry,
                    chunk_qty=available,
                    usable=usable,
                    snap=snap,
                    transferable_qty=lot_pos.transferable,
                )
                if not feas.feasible:
                    continue

                qty = min(usable, remaining)
                if qty <= 0:
                    continue

                used[used_key] = already_used + qty
                dst_allocated[(dst_id, drug_code)] = prev_alloc + qty
                remaining -= qty

                orders.append(TransferOrder(
                    id=f"ORD-GF-{len(orders)+1:03d}",
                    src_facility_id=src_id,
                    dst_facility_id=dst_id,
                    drug_code=drug_code,
                    drug_name=drug.name,
                    batch_no=lot_pos.batch_no,
                    qty=qty,
                    usable=qty,
                    score=round(usable * drug.unit_cost_inr / max(1, shortage_qty), 4),
                    temperature_req="cold_chain" if drug.cold_chain else "ambient",
                ))

    return orders


def _sorted_shortages(snap: Snapshot) -> list[tuple[str, str, int]]:
    """Shortages from snap.positions, sorted by VEN priority (desc) then size (desc)."""
    shortages: list[tuple[str, str, int, int]] = []
    for (fac_id, drug_code), pos in snap.positions.items():
        if pos.shortage > 0:
            drug = snap.drugs.get(drug_code)
            pi = drug.ven_priority if drug else 0
            shortages.append((fac_id, drug_code, pos.shortage, pi))

    shortages.sort(key=lambda x: (x[3], x[2]), reverse=True)
    return [(s[0], s[1], s[2]) for s in shortages]


def _nearest_sources_with_atrisk(
    snap: Snapshot,
    positions: dict[tuple[str, str], PositionResult],
    drug_code: str,
    dst_id: str,
) -> list[tuple[str, float, PositionResult]]:
    """Sources with at-risk stock, sorted by distance to dst."""
    sources: list[tuple[str, float, PositionResult]] = []
    for (fac_id, dc), pos in positions.items():
        if dc != drug_code or fac_id == dst_id:
            continue
        if pos.at_risk <= 0:
            continue
        route = snap.routes.get((fac_id, dst_id))
        dist = route.distance_km if route else float("inf")
        sources.append((fac_id, dist, pos))
    sources.sort(key=lambda x: x[1])
    return sources


def _find_lot(snap: Snapshot, fac_id: str, drug_code: str, batch_no: str):
    for lot in snap.lots_by_fd.get((fac_id, drug_code), []):
        if lot.batch_no == batch_no:
            return lot
    return None
