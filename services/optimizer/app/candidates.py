"""Chunk splitting, usable computation, and candidate generation."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from medbal_common.fefo import compute_position, LotPosition

from .feasibility import BUFFER_DAYS, check_feasibility, FeasibilityResult
from .positions import dst_stock_expiring_before
from .snapshot import Snapshot, Lot, Drug


@dataclass
class Chunk:
    lot: Lot
    index: int
    qty: int
    chunk_id: str = ""

    def __post_init__(self):
        if not self.chunk_id:
            self.chunk_id = f"{self.lot.facility_id}:{self.lot.drug_code}:{self.lot.batch_no}:c{self.index}"


@dataclass
class Candidate:
    chunk: Chunk
    destination_id: str
    drug_code: str
    usable: int
    reward: float
    trip_cost: float
    net_score: float
    feasibility: FeasibilityResult
    selected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk.chunk_id,
            "lot": {
                "facility_id": self.chunk.lot.facility_id,
                "drug_code": self.chunk.lot.drug_code,
                "batch_no": self.chunk.lot.batch_no,
                "expiry": self.chunk.lot.expiry.isoformat(),
                "qty": self.chunk.lot.qty,
            },
            "destination_id": self.destination_id,
            "drug_code": self.drug_code,
            "chunk_qty": self.chunk.qty,
            "usable": self.usable,
            "score": round(self.net_score, 4),
            "feasibility": self.feasibility.rules,
            "selected": self.selected,
        }


def split_chunks(transferable: int, pack_size: int) -> list[int]:
    """Split transferable qty into <=3 chunks (50/25/25%, pack-rounded). Drop zeros."""
    if transferable <= 0:
        return []
    if pack_size < 1:
        pack_size = 1

    c1 = (transferable * 50 // 100 // pack_size) * pack_size
    c2 = (transferable * 25 // 100 // pack_size) * pack_size
    remainder = transferable - c1 - c2
    c3 = (remainder // pack_size) * pack_size

    chunks = [c for c in [c1, c2, c3] if c > 0]

    if not chunks and transferable >= pack_size:
        chunks = [(transferable // pack_size) * pack_size]
    elif not chunks and transferable > 0 and pack_size == 1:
        chunks = [transferable]

    return chunks


def compute_usable(
    chunk_qty: int,
    lot_expiry: date,
    dst_rate: float,
    today: date,
    transit_days: float,
    dst_earlier_stock: int,
) -> int:
    """Usable(k,d) = min(q_k, max(0, r_d*(expiry-today-transit-buffer) - S_d(<expiry)))"""
    remaining_shelf = (lot_expiry - today).days - transit_days - BUFFER_DAYS
    if remaining_shelf <= 0:
        return 0
    capacity = dst_rate * remaining_shelf
    return min(chunk_qty, max(0, int(capacity - dst_earlier_stock)))


def generate_candidates(
    snap: Snapshot,
    positions: dict[tuple[str, str], Any],
    *,
    top_k_destinations: int = 3,
) -> list[Candidate]:
    """Generate all (chunk, destination) candidates with feasibility and scores."""
    all_candidates: list[Candidate] = []

    shortage_dsts: dict[str, list[tuple[str, int]]] = {}
    for (fac_id, drug_code), pos in snap.positions.items():
        if pos.shortage > 0:
            shortage_dsts.setdefault(drug_code, []).append((fac_id, pos.shortage))

    for (fac_id, drug_code), lots in snap.lots_by_fd.items():
        drug = snap.drugs.get(drug_code)
        if not drug:
            continue

        pos_result = positions.get((fac_id, drug_code))
        if pos_result is None:
            continue

        for lot_pos in pos_result.lots:
            if lot_pos.transferable <= 0:
                continue

            lot = None
            for l in lots:
                if l.batch_no == lot_pos.batch_no:
                    lot = l
                    break
            if not lot:
                continue

            chunk_qtys = split_chunks(lot_pos.transferable, drug.pack_size)
            chunks = [Chunk(lot=lot, index=i, qty=q) for i, q in enumerate(chunk_qtys)]

            destinations = _candidate_destinations(snap, drug_code, fac_id)

            for dst_id in destinations:
                route = snap.routes.get((fac_id, dst_id))
                if not route:
                    continue

                dst_pos = snap.positions.get((dst_id, drug_code))
                dst_rate = dst_pos.rate if dst_pos else 0.0
                dst_shortage = dst_pos.shortage if dst_pos else 0
                dst_earlier = dst_stock_expiring_before(snap, dst_id, drug_code, lot.expiry)

                base_usable = compute_usable(
                    lot_pos.transferable, lot.expiry,
                    dst_rate, snap.today, route.transit_days, dst_earlier,
                )

                cumulative = 0
                for chunk in chunks:
                    seq_usable = min(chunk.qty, max(0, base_usable - cumulative))

                    feas = check_feasibility(
                        src_facility_id=fac_id,
                        dst_facility_id=dst_id,
                        drug_code=drug_code,
                        lot_expiry=lot.expiry,
                        chunk_qty=chunk.qty,
                        usable=seq_usable,
                        snap=snap,
                        transferable_qty=lot_pos.transferable,
                        reserve=pos_result.reserve,
                    )

                    reward = seq_usable * drug.unit_cost_inr
                    trip_cost = route.cost_cold_inr if drug.cold_chain else route.cost_ambient_inr
                    net = reward - trip_cost

                    all_candidates.append(Candidate(
                        chunk=chunk,
                        destination_id=dst_id,
                        drug_code=drug_code,
                        usable=seq_usable,
                        reward=reward,
                        trip_cost=trip_cost,
                        net_score=net,
                        feasibility=feas,
                    ))

                    if feas.feasible:
                        cumulative += seq_usable

    _select_top_k(all_candidates, top_k_destinations)
    return all_candidates


def _candidate_destinations(snap: Snapshot, drug_code: str, src_id: str) -> list[str]:
    """All facilities (except source) that have a position for this drug."""
    dsts = []
    for (fac_id, dc) in snap.positions:
        if dc == drug_code and fac_id != src_id:
            dsts.append(fac_id)
    return dsts


def _select_top_k(candidates: list[Candidate], k: int) -> None:
    """Mark top-k destinations per chunk by net_score (feasible only)."""
    by_chunk: dict[str, list[Candidate]] = {}
    for c in candidates:
        by_chunk.setdefault(c.chunk.chunk_id, []).append(c)

    for chunk_id, chunk_cands in by_chunk.items():
        feasible = sorted(
            [c for c in chunk_cands if c.feasibility.feasible],
            key=lambda c: c.net_score,
            reverse=True,
        )
        top_dsts = {c.destination_id for c in feasible[:k]}
        for c in chunk_cands:
            c.selected = c.destination_id in top_dsts and c.feasibility.feasible
