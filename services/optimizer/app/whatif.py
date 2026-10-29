"""What-if sandbox: apply hypothetical overrides to a snapshot copy and re-plan.

Never persists results as a live plan. Returns the diff vs the current plan.
"""
from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass
from typing import Any

from .baselines import TransferOrder, greedy_f4
from .candidates import generate_candidates, Candidate
from .metrics import compute_metrics, PlanMetrics
from .positions import compute_all_positions
from .qubo_builder import build_qubo, QUBOConfig
from .snapshot import Snapshot, Route, Facility, Vehicle, Position
from .solvers import solve_chain
from .validator import apply_plan


@dataclass
class WhatIfOverride:
    action: str
    params: dict[str, Any]


def _apply_overrides(snap: Snapshot, overrides: list[dict[str, Any]]) -> Snapshot:
    """Apply overrides to a deep-copied snapshot. Returns the modified copy."""
    s = _deep_copy(snap)

    for ov in overrides:
        action = ov.get("action", "")

        if action == "add_vehicle":
            vid = ov.get("id", f"V-WI-{uuid.uuid4().hex[:4]}")
            s.vehicles.append(Vehicle(
                id=vid,
                name=ov.get("name", vid),
                cold_chain=ov.get("cold_chain", False),
                capacity_units=ov.get("capacity_units", 10000),
            ))

        elif action == "close_route":
            src = ov.get("src")
            dst = ov.get("dst")
            if src and dst:
                s.routes.pop((src, dst), None)

        elif action == "open_route":
            src = ov.get("src")
            dst = ov.get("dst")
            if src and dst:
                s.routes[(src, dst)] = Route(
                    src=src, dst=dst,
                    distance_km=float(ov.get("distance_km", 10.0)),
                    transit_hours=float(ov.get("transit_hours", 1.0)),
                    cold_chain=ov.get("cold_chain", False),
                    cost_ambient_inr=float(ov.get("cost_ambient_inr", 50.0)),
                    cost_cold_inr=float(ov.get("cost_cold_inr", 120.0)),
                )

        elif action == "set_reserve_days":
            fac = ov.get("facility")
            drug = ov.get("drug")
            days = ov.get("days", 7)
            key = (fac, drug) if fac and drug else None
            if key and key in s.policies:
                pol = s.policies[key]
                s.policies[key] = type(pol)(
                    facility_id=pol.facility_id,
                    drug_code=pol.drug_code,
                    min_reserve_days=days,
                    target_days=pol.target_days,
                    lead_time_days=pol.lead_time_days,
                )

        elif action == "delay_days":
            days = int(ov.get("days", 0))
            from datetime import timedelta
            s.today = s.today + timedelta(days=days)

        elif action == "repair_cold_storage":
            fac_id = ov.get("facility")
            if fac_id and fac_id in s.facilities:
                old = s.facilities[fac_id]
                s.facilities[fac_id] = Facility(
                    id=old.id, name=old.name, level=old.level,
                    cold_storage=True,
                )

        elif action == "break_cold_storage":
            fac_id = ov.get("facility")
            if fac_id and fac_id in s.facilities:
                old = s.facilities[fac_id]
                s.facilities[fac_id] = Facility(
                    id=old.id, name=old.name, level=old.level,
                    cold_storage=False,
                )

        elif action == "set_multiplier":
            fac = ov.get("facility")
            drug = ov.get("drug")
            x = float(ov.get("x", 1.0))
            key = (fac, drug) if fac and drug else None
            if key and key in s.positions:
                pos = s.positions[key]
                new_rate = pos.rate * x
                new_shortage = max(0, int(new_rate * pos.target_days) - pos.effective_stock)
                s.positions[key] = Position(
                    facility_id=pos.facility_id,
                    drug_code=pos.drug_code,
                    effective_stock=pos.effective_stock,
                    at_risk=pos.at_risk,
                    reserve=pos.reserve,
                    shortage=new_shortage,
                    rate=new_rate,
                    target_days=pos.target_days,
                )

        elif action == "remove_vehicle":
            vid = ov.get("id")
            if vid:
                s.vehicles = [v for v in s.vehicles if v.id != vid]

    return s


def run_whatif(
    overrides: list[dict[str, Any]],
    snap: Snapshot,
    live_orders: list[TransferOrder],
    live_metrics: PlanMetrics | None = None,
    *,
    solver: str = "qubo",
    qubo_overrides: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Run the full pipeline on a modified snapshot. Return diff vs live plan."""
    t0 = time.perf_counter()

    wi_snap = _apply_overrides(snap, overrides)
    positions = compute_all_positions(wi_snap)
    candidates = generate_candidates(wi_snap, positions)

    ven_priority = {code: drug.ven_priority for code, drug in wi_snap.drugs.items()}
    shortages = {
        (fac_id, dc): pos.shortage
        for (fac_id, dc), pos in wi_snap.positions.items()
        if pos.shortage > 0
    }

    wi_orders: list[TransferOrder] = []
    solver_meta: dict[str, Any] = {}

    if solver == "qubo":
        config = QUBOConfig(
            p1=qubo_overrides.get("p1", 2.0) if qubo_overrides else 2.0,
            p2=qubo_overrides.get("p2", 1.5) if qubo_overrides else 1.5,
            p3=qubo_overrides.get("p3", 1.0) if qubo_overrides else 1.0,
            gamma=qubo_overrides.get("gamma") if qubo_overrides else None,
        )
        qubo_result = build_qubo(candidates, ven_priority, shortages, config)

        if qubo_result.num_variables > 0:
            from medbal_common.settings import settings
            solve_result = solve_chain(
                qubo_result.Q, qubo_result.offset, qubo_result.num_variables,
                top_k=3, timeout=timeout,
            )
            if solve_result.samples:
                best = solve_result.samples[0]
                selected_pairs = [
                    (qubo_result.variables[v], candidates[qubo_result.variables[v]])
                    for v, val in best.x.items()
                    if val == 1 and v < len(qubo_result.variables)
                ]
                val_result = apply_plan(wi_snap, selected_pairs)
                for vo in val_result.orders:
                    if vo.dropped:
                        continue
                    drug = wi_snap.drugs.get(vo.drug_code)
                    wi_orders.append(TransferOrder(
                        id=f"ORD-WI-{len(wi_orders)+1:03d}",
                        src_facility_id=vo.src_facility_id,
                        dst_facility_id=vo.dst_facility_id,
                        drug_code=vo.drug_code,
                        drug_name=drug.name if drug else vo.drug_code,
                        batch_no=vo.batch_no,
                        qty=vo.qty,
                        usable=vo.usable,
                        score=round(best.energy, 4),
                        temperature_req="cold_chain" if (drug and drug.cold_chain) else "ambient",
                    ))
                solver_meta = {"solver_tier": solve_result.tier, "energy": best.energy}

    if not wi_orders:
        wi_orders = greedy_f4(wi_snap)
        solver_meta = {"solver_tier": "greedy-f4-fallback"}

    wi_metrics = compute_metrics(wi_orders, wi_snap)

    if live_metrics is None:
        live_metrics = compute_metrics(live_orders, snap)

    diff = _compute_diff(live_orders, wi_orders, live_metrics, wi_metrics)
    diff["solver_meta"] = solver_meta
    diff["time_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    diff["overrides_applied"] = [ov.get("action") for ov in overrides]
    diff["whatif_orders"] = [o.to_dict() for o in wi_orders]

    return diff


def _compute_diff(
    live_orders: list[TransferOrder],
    wi_orders: list[TransferOrder],
    live_metrics: PlanMetrics,
    wi_metrics: PlanMetrics,
) -> dict[str, Any]:
    """Compute structural diff between live and what-if plans."""
    live_set = {
        (o.src_facility_id, o.dst_facility_id, o.drug_code, o.batch_no)
        for o in live_orders
    }
    wi_set = {
        (o.src_facility_id, o.dst_facility_id, o.drug_code, o.batch_no)
        for o in wi_orders
    }

    added_keys = wi_set - live_set
    removed_keys = live_set - wi_set
    common_keys = live_set & wi_set

    changes: list[dict[str, Any]] = []

    for key in added_keys:
        o = next(
            o for o in wi_orders
            if (o.src_facility_id, o.dst_facility_id, o.drug_code, o.batch_no) == key
        )
        changes.append({
            "type": "added",
            "order_id": o.id,
            "src": o.src_facility_id,
            "dst": o.dst_facility_id,
            "drug": o.drug_code,
            "batch": o.batch_no,
            "qty": o.qty,
        })

    for key in removed_keys:
        o = next(
            o for o in live_orders
            if (o.src_facility_id, o.dst_facility_id, o.drug_code, o.batch_no) == key
        )
        changes.append({
            "type": "removed",
            "order_id": o.id,
            "src": o.src_facility_id,
            "dst": o.dst_facility_id,
            "drug": o.drug_code,
            "batch": o.batch_no,
            "qty": o.qty,
        })

    for key in common_keys:
        lo = next(
            o for o in live_orders
            if (o.src_facility_id, o.dst_facility_id, o.drug_code, o.batch_no) == key
        )
        wo = next(
            o for o in wi_orders
            if (o.src_facility_id, o.dst_facility_id, o.drug_code, o.batch_no) == key
        )
        if lo.qty != wo.qty or lo.usable != wo.usable:
            changes.append({
                "type": "changed",
                "order_id": lo.id,
                "src": lo.src_facility_id,
                "dst": lo.dst_facility_id,
                "drug": lo.drug_code,
                "batch": lo.batch_no,
                "qty_old": lo.qty,
                "qty_new": wo.qty,
                "usable_old": lo.usable,
                "usable_new": wo.usable,
            })

    return {
        "changes": changes,
        "orders_added": len(added_keys),
        "orders_removed": len(removed_keys),
        "orders_changed": len([c for c in changes if c["type"] == "changed"]),
        "kpi_delta": {
            "shortage_reduction": round(wi_metrics.shortage_reduction - live_metrics.shortage_reduction, 4),
            "expiry_avoided": wi_metrics.expiry_avoided_units - live_metrics.expiry_avoided_units,
            "cost_inr": round(wi_metrics.total_cost_inr - live_metrics.total_cost_inr, 2),
            "trips": wi_metrics.trips - live_metrics.trips,
        },
        "kpi_whatif": wi_metrics.to_dict(),
        "kpi_live": live_metrics.to_dict(),
    }


def _deep_copy(snap: Snapshot) -> Snapshot:
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
