from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class Facility(BaseModel):
    id: str
    name: str
    type: str
    lat: float
    lon: float
    cold_storage: bool = False


class Drug(BaseModel):
    code: str
    name: str
    ven: Literal["V", "E", "N"]
    unit: str
    pack_size: int
    cold_chain: bool = False
    controlled: bool = False
    min_residual_days: int = 30


class Lot(BaseModel):
    facility_id: str
    drug_code: str
    batch_no: str
    expiry: date
    qty: int


class Route(BaseModel):
    src_facility_id: str
    dst_facility_id: str
    distance_km: float
    transit_hours: float
    cold_chain: bool = False


class Vehicle(BaseModel):
    id: str
    name: str
    cold_chain: bool = False
    capacity_units: int


class Position(BaseModel):
    facility_id: str
    drug_code: str
    effective_stock: int
    at_risk: int
    reserve: int
    shortage: int


class Candidate(BaseModel):
    lot: Lot
    destination_id: str
    usable: int
    score: float


class TransferOrder(BaseModel):
    id: str
    dta_number: str
    src_facility_id: str
    dst_facility_id: str
    items: list[dict]
    status: str


class CustodyEvent(BaseModel):
    order_id: str
    event_type: str
    actor: str
    timestamp: datetime
    location: str | None = None


class PlanRun(BaseModel):
    id: str
    created_at: datetime
    solver_tier: str
    energy: float | None = None
    gap_to_milp: float | None = None
    transfers: int
    shortage_reduction: float
