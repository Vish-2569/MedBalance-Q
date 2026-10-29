"""Compute plan metrics: shortage reduction, expiry avoided, trips, km, cost."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .baselines import TransferOrder
from .snapshot import Snapshot


@dataclass
class PlanMetrics:
    shortage_reduction: float
    expiry_avoided_units: int
    expiry_avoided_inr: float
    trips: int
    total_km: float
    total_cost_inr: float
    per_dst_drug: dict[tuple[str, str], dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "shortage_reduction": round(self.shortage_reduction, 4),
            "expiry_avoided": self.expiry_avoided_units,
            "expiry_avoided_inr": round(self.expiry_avoided_inr, 2),
            "trips": self.trips,
            "total_km": round(self.total_km, 1),
            "cost_inr": round(self.total_cost_inr, 2),
        }


def compute_metrics(orders: list[TransferOrder], snap: Snapshot) -> PlanMetrics:
    """Compute aggregate metrics for a set of transfer orders."""
    total_shortage_before: int = 0
    total_shortage_after: int = 0
    per_dst_drug: dict[tuple[str, str], dict[str, Any]] = {}
    transfers_by_dd: dict[tuple[str, str], int] = {}

    for (fac_id, drug_code), pos in snap.positions.items():
        if pos.shortage > 0:
            total_shortage_before += pos.shortage

    for o in orders:
        key = (o.dst_facility_id, o.drug_code)
        transfers_by_dd[key] = transfers_by_dd.get(key, 0) + o.usable

    for (fac_id, drug_code), pos in snap.positions.items():
        if pos.shortage > 0:
            supplied = transfers_by_dd.get((fac_id, drug_code), 0)
            after = max(0, pos.shortage - supplied)
            total_shortage_after += after
            if supplied > 0:
                per_dst_drug[(fac_id, drug_code)] = {
                    "shortage_before": pos.shortage,
                    "shortage_after": after,
                    "supplied": supplied,
                }

    if total_shortage_before > 0:
        shortage_reduction = 1.0 - (total_shortage_after / total_shortage_before)
    else:
        shortage_reduction = 0.0

    expiry_avoided_units = 0
    expiry_avoided_inr = 0.0
    for o in orders:
        drug = snap.drugs.get(o.drug_code)
        expiry_avoided_units += o.usable
        if drug:
            expiry_avoided_inr += o.usable * drug.unit_cost_inr

    trips_set: set[tuple[str, str]] = set()
    total_km = 0.0
    total_cost = 0.0
    for o in orders:
        route = snap.routes.get((o.src_facility_id, o.dst_facility_id))
        trip_key = (o.src_facility_id, o.dst_facility_id)
        if trip_key not in trips_set:
            trips_set.add(trip_key)
            if route:
                total_km += route.distance_km
                drug = snap.drugs.get(o.drug_code)
                if drug and drug.cold_chain:
                    total_cost += route.cost_cold_inr
                else:
                    total_cost += route.cost_ambient_inr

    return PlanMetrics(
        shortage_reduction=shortage_reduction,
        expiry_avoided_units=expiry_avoided_units,
        expiry_avoided_inr=expiry_avoided_inr,
        trips=len(trips_set),
        total_km=total_km,
        total_cost_inr=total_cost,
        per_dst_drug=per_dst_drug,
    )
