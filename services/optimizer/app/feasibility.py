"""Feasibility rules F1–F6 as defined in CLAUDE.md §5-§6."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .snapshot import Snapshot, Drug, Route

BUFFER_DAYS = 1


@dataclass
class FailedRule:
    rule: str
    detail: str


@dataclass
class FeasibilityResult:
    feasible: bool
    failed_rules: list[FailedRule]
    rules: dict[str, bool]


def check_feasibility(
    src_facility_id: str,
    dst_facility_id: str,
    drug_code: str,
    lot_expiry: date,
    chunk_qty: int,
    usable: int,
    snap: Snapshot,
    *,
    transferable_qty: int | None = None,
    reserve: int = 0,
    source_qty: int = 0,
) -> FeasibilityResult:
    """Check F1–F6 for a (chunk, destination) pair. Pure function."""
    failed: list[FailedRule] = []
    rules: dict[str, bool] = {}

    drug = snap.drugs.get(drug_code)

    # F1: Identity — drug exists and is the same drug
    f1 = drug is not None and src_facility_id != dst_facility_id
    rules["F1"] = f1
    if not f1:
        if drug is None:
            failed.append(FailedRule("F1", f"Unknown drug code {drug_code}"))
        else:
            failed.append(FailedRule("F1", "Source and destination are the same facility"))

    # F2: Route exists
    route = snap.routes.get((src_facility_id, dst_facility_id))
    f2 = route is not None
    rules["F2"] = f2
    if not f2:
        failed.append(FailedRule("F2", f"No route from {src_facility_id} to {dst_facility_id}"))

    # F3: Cold chain
    if drug and drug.cold_chain:
        dst_fac = snap.facilities.get(dst_facility_id)
        cold_route = route.cold_chain if route else False
        cold_vehicle = any(v.cold_chain for v in snap.vehicles)
        cold_storage = dst_fac.cold_storage if dst_fac else False
        f3 = cold_route and cold_vehicle and cold_storage
        rules["F3"] = f3
        if not f3:
            details = []
            if not cold_route:
                details.append("route not cold-capable")
            if not cold_vehicle:
                details.append("no cold vehicle available")
            if not cold_storage:
                details.append("destination lacks cold storage")
            failed.append(FailedRule("F3", "; ".join(details)))
    else:
        rules["F3"] = True

    # F4: Usable > 0 and residual shelf life >= min_residual_days
    if drug and route:
        transit_days = route.transit_days
        residual = (lot_expiry - snap.today).days - transit_days - BUFFER_DAYS
        min_residual = drug.min_residual_days
        f4 = usable > 0 and residual >= min_residual
        rules["F4"] = f4
        if not f4:
            details = []
            if usable <= 0:
                details.append(f"usable=0 at destination")
            if residual < min_residual:
                details.append(
                    f"residual shelf life {residual:.0f}d < min {min_residual}d"
                )
            failed.append(FailedRule("F4", "; ".join(details)))
    elif drug:
        rules["F4"] = False
        failed.append(FailedRule("F4", "Cannot compute without route"))
    else:
        rules["F4"] = False

    # F5: Reserve — transfer must not violate source reserve
    if transferable_qty is not None:
        f5 = chunk_qty <= transferable_qty
        rules["F5"] = f5
        if not f5:
            failed.append(FailedRule(
                "F5",
                f"chunk {chunk_qty} > transferable {transferable_qty} (reserve protected)",
            ))
    else:
        rules["F5"] = True

    # F6: Not controlled
    if drug:
        f6 = not drug.controlled
        rules["F6"] = f6
        if not f6:
            failed.append(FailedRule("F6", f"{drug_code} is a controlled substance"))
    else:
        rules["F6"] = False

    feasible = all(rules.values())
    return FeasibilityResult(feasible=feasible, failed_rules=failed, rules=rules)


def check_f1_f3_only(
    src_facility_id: str,
    dst_facility_id: str,
    drug_code: str,
    snap: Snapshot,
) -> FeasibilityResult:
    """Lightweight check for greedy_phone_call: F1, F2, F3 only."""
    failed: list[FailedRule] = []
    rules: dict[str, bool] = {}

    drug = snap.drugs.get(drug_code)

    f1 = drug is not None and src_facility_id != dst_facility_id
    rules["F1"] = f1
    if not f1:
        if drug is None:
            failed.append(FailedRule("F1", f"Unknown drug code {drug_code}"))
        else:
            failed.append(FailedRule("F1", "Same facility"))

    route = snap.routes.get((src_facility_id, dst_facility_id))
    f2 = route is not None
    rules["F2"] = f2
    if not f2:
        failed.append(FailedRule("F2", f"No route {src_facility_id}->{dst_facility_id}"))

    if drug and drug.cold_chain:
        dst_fac = snap.facilities.get(dst_facility_id)
        cold_route = route.cold_chain if route else False
        cold_vehicle = any(v.cold_chain for v in snap.vehicles)
        cold_storage = dst_fac.cold_storage if dst_fac else False
        f3 = cold_route and cold_vehicle and cold_storage
        rules["F3"] = f3
        if not f3:
            failed.append(FailedRule("F3", "Cold chain not met"))
    else:
        rules["F3"] = True

    return FeasibilityResult(feasible=all(rules.values()), failed_rules=failed, rules=rules)
