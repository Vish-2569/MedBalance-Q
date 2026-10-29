"""In-memory snapshot of district state, indexed for fast lookup."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Facility:
    id: str
    name: str
    level: str
    cold_storage: bool


@dataclass(frozen=True)
class Drug:
    code: str
    name: str
    ven: str
    unit: str
    pack_size: int
    cold_chain: bool
    controlled: bool
    min_residual_days: int
    unit_cost_inr: float

    @property
    def ven_priority(self) -> int:
        return {"V": 3, "E": 2, "N": 1}.get(self.ven, 0)


@dataclass(frozen=True)
class Route:
    src: str
    dst: str
    distance_km: float
    transit_hours: float
    cold_chain: bool
    cost_ambient_inr: float = 0.0
    cost_cold_inr: float = 0.0

    @property
    def transit_days(self) -> float:
        return self.transit_hours / 24.0


@dataclass(frozen=True)
class Vehicle:
    id: str
    name: str
    cold_chain: bool
    capacity_units: int


@dataclass(frozen=True)
class Lot:
    facility_id: str
    drug_code: str
    batch_no: str
    expiry: date
    qty: int


@dataclass
class Position:
    facility_id: str
    drug_code: str
    effective_stock: int
    at_risk: int
    reserve: int
    shortage: int
    rate: float
    target_days: int


@dataclass
class Policy:
    facility_id: str
    drug_code: str
    min_reserve_days: int = 7
    target_days: int = 21
    lead_time_days: int = 3


@dataclass
class Snapshot:
    today: date
    facilities: dict[str, Facility] = field(default_factory=dict)
    drugs: dict[str, Drug] = field(default_factory=dict)
    routes: dict[tuple[str, str], Route] = field(default_factory=dict)
    vehicles: list[Vehicle] = field(default_factory=list)
    lots: list[Lot] = field(default_factory=list)
    lots_by_fd: dict[tuple[str, str], list[Lot]] = field(default_factory=dict)
    positions: dict[tuple[str, str], Position] = field(default_factory=dict)
    policies: dict[tuple[str, str], Policy] = field(default_factory=dict)


def _parse_date(v: Any) -> date:
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def build_snapshot(data: dict[str, Any], today: date | None = None) -> Snapshot:
    snap = Snapshot(today=today or date.today())

    for f in data.get("facilities", []):
        fac = Facility(
            id=f["id"],
            name=f.get("name", f["id"]),
            level=f.get("level", f.get("type", "hospital")),
            cold_storage=f.get("cold_storage", f.get("cold_storage_ok", True)),
        )
        snap.facilities[fac.id] = fac

    for d in data.get("drugs", []):
        drug = Drug(
            code=d["code"],
            name=d.get("name", d["code"]),
            ven=d.get("ven", "N"),
            unit=d.get("unit", "unit"),
            pack_size=d.get("pack_size", 1),
            cold_chain=d.get("cold_chain", False),
            controlled=d.get("controlled", False),
            min_residual_days=d.get("min_residual_days", 30),
            unit_cost_inr=float(d.get("unit_cost_inr", 0)),
        )
        snap.drugs[drug.code] = drug

    for r in data.get("routes", []):
        route = Route(
            src=r["src_facility_id"],
            dst=r["dst_facility_id"],
            distance_km=float(r.get("distance_km", 0)),
            transit_hours=float(r.get("transit_hours", 0)),
            cold_chain=r.get("cold_chain", False),
            cost_ambient_inr=float(r.get("cost_ambient_inr", 0)),
            cost_cold_inr=float(r.get("cost_cold_inr", 0)),
        )
        snap.routes[(route.src, route.dst)] = route

    for v in data.get("vehicles", []):
        snap.vehicles.append(Vehicle(
            id=v["id"],
            name=v.get("name", v["id"]),
            cold_chain=v.get("cold_chain", False),
            capacity_units=v.get("capacity_units", 10000),
        ))

    for lo in data.get("lots", []):
        lot = Lot(
            facility_id=lo["facility_id"],
            drug_code=lo["drug_code"],
            batch_no=lo["batch_no"],
            expiry=_parse_date(lo["expiry"]),
            qty=lo["qty"],
        )
        snap.lots.append(lot)
        key = (lot.facility_id, lot.drug_code)
        snap.lots_by_fd.setdefault(key, []).append(lot)

    for p in data.get("positions", []):
        pos = Position(
            facility_id=p["facility_id"],
            drug_code=p["drug_code"],
            effective_stock=p.get("effective_stock", 0),
            at_risk=p.get("at_risk", 0),
            reserve=p.get("reserve", 0),
            shortage=p.get("shortage", 0),
            rate=float(p.get("consumption_rate", p.get("rate", 0))),
            target_days=p.get("target_days", 21),
        )
        snap.positions[(pos.facility_id, pos.drug_code)] = pos

    for pol in data.get("policies", []):
        policy = Policy(
            facility_id=pol["facility_id"],
            drug_code=pol["drug_code"],
            min_reserve_days=pol.get("min_reserve_days", 7),
            target_days=pol.get("target_days", 21),
            lead_time_days=pol.get("lead_time_days", 3),
        )
        snap.policies[(policy.facility_id, policy.drug_code)] = policy

    return snap


def fetch_snapshot(core_api_url: str) -> dict[str, Any]:
    import httpx
    resp = httpx.get(f"{core_api_url}/snapshot", timeout=10.0)
    resp.raise_for_status()
    return resp.json()
