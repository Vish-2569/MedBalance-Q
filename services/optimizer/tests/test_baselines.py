"""Baseline solvers: greedy_phone_call vs greedy_f4."""
from __future__ import annotations

from datetime import date

import pytest

from app.baselines import greedy_phone_call, greedy_f4
from app.metrics import compute_metrics
from app.positions import compute_all_positions
from app.snapshot import build_snapshot


def test_greedy_f4_no_infeasible_orders(base_snapshot):
    """greedy_f4 should only produce orders that pass all feasibility rules."""
    orders = greedy_f4(base_snapshot)
    assert len(orders) > 0
    for o in orders:
        assert o.usable > 0, f"Order {o.id} has usable=0"
        assert o.qty > 0


def test_greedy_f4_controlled_never_candidate(base_snapshot):
    """Controlled drug (MORPHINE) should never appear in any order."""
    orders = greedy_f4(base_snapshot)
    for o in orders:
        assert o.drug_code != "MORPHINE", f"Controlled drug in order {o.id}"


def test_greedy_phone_call_controlled_never_candidate(base_snapshot):
    """Even phone_call respects F1-F3; controlled drugs might pass F1-F3
    but the phone_call logic only picks from at-risk lots for shortages."""
    orders = greedy_phone_call(base_snapshot)
    for o in orders:
        assert o.drug_code != "MORPHINE"


def test_reserve_never_violated(base_snapshot):
    """No transfer should take from reserved stock."""
    positions = compute_all_positions(base_snapshot)
    orders = greedy_f4(base_snapshot)

    taken: dict[tuple[str, str, str], int] = {}
    for o in orders:
        key = (o.src_facility_id, o.drug_code, o.batch_no)
        taken[key] = taken.get(key, 0) + o.qty

    for (fac, drug, batch), qty_taken in taken.items():
        pos = positions.get((fac, drug))
        if pos:
            for lp in pos.lots:
                if lp.batch_no == batch:
                    assert qty_taken <= lp.transferable, (
                        f"Took {qty_taken} from {batch} but transferable={lp.transferable}"
                    )


def test_phone_call_can_move_waste_f4_does_not():
    """Construct a scenario where phone_call moves stock that F4 would reject.

    H4 has insulin expiring in 18 days. min_residual_days=60.
    Route H4->H1 exists (non-cold).
    H1 has insulin shortage.

    phone_call: finds at-risk at H4, shortage at H1, checks F1-F3.
      - F1: insulin=insulin OK
      - F2: route H4->H1 exists OK
      - F3: cold drug but route is non-cold -> FAIL

    So for cold-chain drugs, both fail on F3. Let's use a non-cold drug scenario instead.

    Use a non-cold drug with very short expiry and high min_residual_days:
    - SRC has drug X, qty=100, expiry in 10 days. min_residual_days=30.
    - DST has shortage of drug X.
    - phone_call moves it (only checks F1-F3, all pass).
    - greedy_f4 rejects it (F4: residual 10-transit-buffer < 30).
    """
    today = date(2026, 11, 1)
    data = {
        "facilities": [
            {"id": "SRC", "name": "Source", "type": "DH", "cold_storage": True},
            {"id": "DST", "name": "Dest", "type": "TH", "cold_storage": True},
        ],
        "drugs": [
            {"code": "SHORT_LIFE", "name": "Short Life Drug", "ven": "V", "unit": "tab",
             "pack_size": 1, "cold_chain": False, "controlled": False,
             "min_residual_days": 30, "unit_cost_inr": 5.0},
        ],
        "routes": [
            {"src_facility_id": "SRC", "dst_facility_id": "DST", "distance_km": 5,
             "transit_hours": 0.5, "cold_chain": False, "cost_ambient_inr": 30, "cost_cold_inr": 0},
        ],
        "vehicles": [
            {"id": "V1", "name": "Van", "cold_chain": False, "capacity_units": 5000},
        ],
        "lots": [
            {"facility_id": "SRC", "drug_code": "SHORT_LIFE", "batch_no": "BX-001",
             "expiry": "2026-11-11", "qty": 100},
        ],
        "positions": [
            {"facility_id": "SRC", "drug_code": "SHORT_LIFE", "consumption_rate": 3.0,
             "effective_stock": 30, "at_risk": 70, "reserve": 11, "shortage": 0, "target_days": 21},
            {"facility_id": "DST", "drug_code": "SHORT_LIFE", "consumption_rate": 5.0,
             "effective_stock": 0, "at_risk": 0, "reserve": 0, "shortage": 105, "target_days": 21},
        ],
    }
    snap = build_snapshot(data, today=today)

    pc_orders = greedy_phone_call(snap)
    f4_orders = greedy_f4(snap)

    # Phone call should produce at least one order (F1-F3 all pass for non-cold drug)
    assert len(pc_orders) > 0, "Phone call should move the at-risk stock"
    assert any(o.drug_code == "SHORT_LIFE" for o in pc_orders)

    # greedy_f4 should NOT produce orders for SHORT_LIFE
    # because residual = 10 - 0.02 - 1 = 8.98 < 30 = min_residual_days
    short_life_f4 = [o for o in f4_orders if o.drug_code == "SHORT_LIFE"]
    assert len(short_life_f4) == 0, (
        f"greedy_f4 should reject SHORT_LIFE (residual < min_residual), "
        f"but produced {len(short_life_f4)} orders"
    )


def test_greedy_f4_produces_valid_plan(base_snapshot):
    """greedy_f4 should produce a plan with positive metrics."""
    orders = greedy_f4(base_snapshot)
    metrics = compute_metrics(orders, base_snapshot)
    assert metrics.shortage_reduction > 0
    assert metrics.expiry_avoided_units > 0
    assert metrics.trips > 0


def test_greedy_f4_respects_cold_chain(base_snapshot):
    """Insulin orders should only go on cold routes to cold-storage destinations."""
    orders = greedy_f4(base_snapshot)
    insulin_orders = [o for o in orders if o.drug_code == "INSULIN"]
    for o in insulin_orders:
        assert o.temperature_req == "cold_chain"
        dst = base_snapshot.facilities[o.dst_facility_id]
        assert dst.cold_storage, f"Insulin sent to {o.dst_facility_id} without cold storage"
        route = base_snapshot.routes.get((o.src_facility_id, o.dst_facility_id))
        assert route and route.cold_chain, f"Insulin on non-cold route"
