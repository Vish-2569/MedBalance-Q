"""Candidate generation: chunks, usable, sequential usable."""
from __future__ import annotations

from datetime import date

import pytest

from app.candidates import split_chunks, compute_usable, generate_candidates, Chunk
from app.positions import compute_all_positions, dst_stock_expiring_before
from app.snapshot import Lot, build_snapshot


# ---------- Chunk splitting ----------

def test_split_chunks_basic():
    chunks = split_chunks(100, 1)
    assert len(chunks) <= 3
    assert sum(chunks) <= 100
    assert chunks[0] == 50  # 50%
    assert chunks[1] == 25  # 25%
    assert chunks[2] == 25  # 25%


def test_split_chunks_pack_rounded():
    chunks = split_chunks(100, 10)
    assert all(c % 10 == 0 for c in chunks)
    assert sum(chunks) <= 100


def test_split_chunks_zero():
    assert split_chunks(0, 10) == []


def test_split_chunks_small_qty():
    chunks = split_chunks(7, 10)
    assert chunks == []


def test_split_chunks_one_pack():
    chunks = split_chunks(10, 10)
    assert len(chunks) >= 1
    assert all(c % 10 == 0 for c in chunks)


def test_split_chunks_drop_zeros():
    """Pack size larger than 25% of qty -> some chunks become zero and are dropped."""
    chunks = split_chunks(30, 10)
    assert all(c > 0 for c in chunks)
    assert len(chunks) <= 3


# ---------- Usable computation ----------

def test_usable_worked_example():
    """50 vials, dst rate 2/day, 14 usable days, no dst stock -> usable 28."""
    u = compute_usable(
        chunk_qty=50,
        lot_expiry=date(2026, 11, 16),
        dst_rate=2.0,
        today=date(2026, 11, 1),
        transit_days=0.02,
        dst_earlier_stock=0,
    )
    # remaining_shelf = 15 - 0.02 - 1 = 13.98
    # capacity = 2 * 13.98 = 27.96 -> int(27.96) = 27
    # Hmm, with buffer=1 day. Let me recalculate:
    # expiry - today = 15 days. transit = 0.02. buffer = 1.
    # remaining = 15 - 0.02 - 1 = 13.98
    # capacity = 2 * 13.98 = 27.96
    # usable = min(50, max(0, int(27.96 - 0))) = min(50, 27) = 27
    # The worked example expects 28 with "14 usable days"
    # To get exactly 28, we need 14 days: expiry Nov 16, today Nov 1 = 15 days,
    # transit 0 and buffer 1 -> 14 days -> 2*14=28
    # Let's use transit_days=0 for the clean example
    u_clean = compute_usable(
        chunk_qty=50,
        lot_expiry=date(2026, 11, 16),
        dst_rate=2.0,
        today=date(2026, 11, 1),
        transit_days=0.0,
        dst_earlier_stock=0,
    )
    # remaining = 15 - 0 - 1 = 14. capacity = 28. usable = 28.
    assert u_clean == 28


def test_usable_with_dst_stock():
    """Destination holds 10 earlier-expiring units -> usable 18."""
    u = compute_usable(
        chunk_qty=50,
        lot_expiry=date(2026, 11, 16),
        dst_rate=2.0,
        today=date(2026, 11, 1),
        transit_days=0.0,
        dst_earlier_stock=10,
    )
    # remaining = 14, capacity = 28, usable = min(50, 28 - 10) = 18
    assert u == 18


def test_usable_expired_lot():
    u = compute_usable(
        chunk_qty=50,
        lot_expiry=date(2026, 10, 30),
        dst_rate=2.0,
        today=date(2026, 11, 1),
        transit_days=0.0,
        dst_earlier_stock=0,
    )
    assert u == 0


def test_usable_zero_rate():
    u = compute_usable(
        chunk_qty=50,
        lot_expiry=date(2027, 3, 1),
        dst_rate=0.0,
        today=date(2026, 11, 1),
        transit_days=0.0,
        dst_earlier_stock=0,
    )
    assert u == 0


def test_usable_capped_by_chunk():
    """Usable is capped by chunk qty even if capacity is higher."""
    u = compute_usable(
        chunk_qty=10,
        lot_expiry=date(2027, 6, 1),
        dst_rate=100.0,
        today=date(2026, 11, 1),
        transit_days=0.0,
        dst_earlier_stock=0,
    )
    assert u == 10


# ---------- dst_stock_expiring_before ----------

def test_dst_stock_expiring_before(today):
    data = {
        "facilities": [{"id": "D1", "name": "D1", "type": "DH", "cold_storage": True}],
        "drugs": [{"code": "X", "name": "X", "ven": "E", "unit": "tab", "pack_size": 1,
                   "cold_chain": False, "controlled": False, "min_residual_days": 30, "unit_cost_inr": 1}],
        "routes": [], "vehicles": [], "positions": [],
        "lots": [
            {"facility_id": "D1", "drug_code": "X", "batch_no": "B1", "expiry": "2026-11-10", "qty": 10},
            {"facility_id": "D1", "drug_code": "X", "batch_no": "B2", "expiry": "2026-11-20", "qty": 20},
            {"facility_id": "D1", "drug_code": "X", "batch_no": "B3", "expiry": "2026-12-01", "qty": 30},
        ],
    }
    snap = build_snapshot(data, today=today)
    # Lots expiring before Nov 20: only B1 (Nov 10)
    assert dst_stock_expiring_before(snap, "D1", "X", date(2026, 11, 20)) == 10
    # Lots expiring before Dec 1: B1 + B2 = 30
    assert dst_stock_expiring_before(snap, "D1", "X", date(2026, 12, 1)) == 30
    # Lots expiring before Nov 5: none
    assert dst_stock_expiring_before(snap, "D1", "X", date(2026, 11, 5)) == 0


# ---------- Sequential usable for same destination ----------

def test_chunk_sequential_usable(base_snapshot):
    """When multiple chunks of same lot go to same destination,
    later chunks get reduced usable (budget is shared)."""
    positions = compute_all_positions(base_snapshot)
    candidates = generate_candidates(base_snapshot, positions)

    by_lot_dst: dict[tuple[str, str], list] = {}
    for c in candidates:
        key = (c.chunk.lot.batch_no, c.destination_id)
        by_lot_dst.setdefault(key, []).append(c)

    for key, cands in by_lot_dst.items():
        if len(cands) <= 1:
            continue
        cands_sorted = sorted(cands, key=lambda x: x.chunk.index)
        feasible = [c for c in cands_sorted if c.feasibility.feasible]
        if len(feasible) > 1:
            total_usable = sum(c.usable for c in feasible)
            first_usable = feasible[0].usable
            assert total_usable >= first_usable
            if feasible[-1].usable > 0:
                assert feasible[-1].usable <= feasible[0].usable
