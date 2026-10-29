from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("USE_FIXTURES", "1")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.snapshot import (
    Snapshot, Facility, Drug, Route, Vehicle, Lot, Position, Policy,
    build_snapshot,
)


@pytest.fixture
def today() -> date:
    return date(2026, 11, 1)


@pytest.fixture
def base_snapshot(today) -> Snapshot:
    """Minimal snapshot matching the seed story for testing."""
    data = {
        "facilities": [
            {"id": "W0", "name": "Warehouse", "type": "WH", "cold_storage": True},
            {"id": "H1", "name": "City Hospital", "type": "DH", "cold_storage": True},
            {"id": "H2", "name": "General Hospital", "type": "TH", "cold_storage": True},
            {"id": "H3", "name": "CHC", "type": "CHC", "cold_storage": False},
            {"id": "H4", "name": "PHC", "type": "PHC", "cold_storage": False},
        ],
        "drugs": [
            {"code": "INSULIN", "name": "Insulin Human 40IU/ml", "ven": "V", "unit": "vial",
             "pack_size": 1, "cold_chain": True, "controlled": False,
             "min_residual_days": 60, "unit_cost_inr": 45.0},
            {"code": "PCM", "name": "Paracetamol 500mg", "ven": "E", "unit": "tablet",
             "pack_size": 10, "cold_chain": False, "controlled": False,
             "min_residual_days": 30, "unit_cost_inr": 0.50},
            {"code": "AMOX", "name": "Amoxicillin 500mg", "ven": "E", "unit": "capsule",
             "pack_size": 10, "cold_chain": False, "controlled": False,
             "min_residual_days": 30, "unit_cost_inr": 2.50},
            {"code": "ORS", "name": "ORS Sachet", "ven": "E", "unit": "sachet",
             "pack_size": 25, "cold_chain": False, "controlled": False,
             "min_residual_days": 30, "unit_cost_inr": 3.50},
            {"code": "MORPHINE", "name": "Morphine Sulphate", "ven": "V", "unit": "ampoule",
             "pack_size": 5, "cold_chain": False, "controlled": True,
             "min_residual_days": 60, "unit_cost_inr": 35.0},
            {"code": "IFA", "name": "Iron Folic Acid", "ven": "E", "unit": "tablet",
             "pack_size": 100, "cold_chain": False, "controlled": False,
             "min_residual_days": 30, "unit_cost_inr": 0.30},
        ],
        "routes": [
            {"src_facility_id": "W0", "dst_facility_id": "H1", "distance_km": 8.5,
             "transit_hours": 0.5, "cold_chain": True, "cost_ambient_inr": 50, "cost_cold_inr": 120},
            {"src_facility_id": "H1", "dst_facility_id": "W0", "distance_km": 8.5,
             "transit_hours": 0.5, "cold_chain": True, "cost_ambient_inr": 50, "cost_cold_inr": 120},
            {"src_facility_id": "W0", "dst_facility_id": "H2", "distance_km": 6.2,
             "transit_hours": 0.4, "cold_chain": True, "cost_ambient_inr": 40, "cost_cold_inr": 100},
            {"src_facility_id": "H2", "dst_facility_id": "W0", "distance_km": 6.2,
             "transit_hours": 0.4, "cold_chain": True, "cost_ambient_inr": 40, "cost_cold_inr": 100},
            {"src_facility_id": "W0", "dst_facility_id": "H3", "distance_km": 12.1,
             "transit_hours": 0.8, "cold_chain": False, "cost_ambient_inr": 70, "cost_cold_inr": 150},
            {"src_facility_id": "H3", "dst_facility_id": "W0", "distance_km": 12.1,
             "transit_hours": 0.8, "cold_chain": False, "cost_ambient_inr": 70, "cost_cold_inr": 150},
            {"src_facility_id": "W0", "dst_facility_id": "H4", "distance_km": 10.3,
             "transit_hours": 0.7, "cold_chain": False, "cost_ambient_inr": 60, "cost_cold_inr": 130},
            {"src_facility_id": "H4", "dst_facility_id": "W0", "distance_km": 10.3,
             "transit_hours": 0.7, "cold_chain": False, "cost_ambient_inr": 60, "cost_cold_inr": 130},
            {"src_facility_id": "H1", "dst_facility_id": "H2", "distance_km": 7.0,
             "transit_hours": 0.5, "cold_chain": True, "cost_ambient_inr": 45, "cost_cold_inr": 110},
            {"src_facility_id": "H2", "dst_facility_id": "H1", "distance_km": 7.0,
             "transit_hours": 0.5, "cold_chain": True, "cost_ambient_inr": 45, "cost_cold_inr": 110},
            {"src_facility_id": "H4", "dst_facility_id": "H1", "distance_km": 5.0,
             "transit_hours": 0.4, "cold_chain": False, "cost_ambient_inr": 35, "cost_cold_inr": 80},
            {"src_facility_id": "H1", "dst_facility_id": "H4", "distance_km": 5.0,
             "transit_hours": 0.4, "cold_chain": False, "cost_ambient_inr": 35, "cost_cold_inr": 80},
        ],
        "vehicles": [
            {"id": "V1", "name": "Cold Van", "cold_chain": True, "capacity_units": 5000},
            {"id": "V2", "name": "Utility Van", "cold_chain": False, "capacity_units": 10000},
        ],
        "lots": [
            # H1: near-zero insulin
            {"facility_id": "H1", "drug_code": "INSULIN", "batch_no": "B-INS-H1-001",
             "expiry": "2026-11-15", "qty": 5},
            # H4: insulin with zero usage, no cold storage, expiry in 18 days
            {"facility_id": "H4", "drug_code": "INSULIN", "batch_no": "B-INS-H4-001",
             "expiry": "2026-11-19", "qty": 50},
            # H2: overstocked PCM
            {"facility_id": "H2", "drug_code": "PCM", "batch_no": "B-PCM-H2-001",
             "expiry": "2026-11-25", "qty": 1500},
            # H2: overstocked AMOX
            {"facility_id": "H2", "drug_code": "AMOX", "batch_no": "B-AMX-H2-001",
             "expiry": "2026-12-05", "qty": 800},
            # H2: overstocked IFA
            {"facility_id": "H2", "drug_code": "IFA", "batch_no": "B-IFA-H2-001",
             "expiry": "2026-12-10", "qty": 3000},
            # H3: low ORS
            {"facility_id": "H3", "drug_code": "ORS", "batch_no": "B-ORS-H3-001",
             "expiry": "2027-01-15", "qty": 20},
            # H2: controlled morphine (F6 block)
            {"facility_id": "H2", "drug_code": "MORPHINE", "batch_no": "B-MOR-H2-001",
             "expiry": "2027-08-15", "qty": 15},
        ],
        "positions": [
            # H1 needs insulin badly
            {"facility_id": "H1", "drug_code": "INSULIN", "consumption_rate": 2.0,
             "effective_stock": 5, "at_risk": 0, "reserve": 6, "shortage": 37, "target_days": 21},
            # H4 has insulin but zero usage
            {"facility_id": "H4", "drug_code": "INSULIN", "consumption_rate": 0.0,
             "effective_stock": 0, "at_risk": 50, "reserve": 0, "shortage": 0, "target_days": 21},
            # H2 has excess PCM
            {"facility_id": "H2", "drug_code": "PCM", "consumption_rate": 30.0,
             "effective_stock": 720, "at_risk": 780, "reserve": 108, "shortage": 0, "target_days": 21},
            # H1 needs PCM
            {"facility_id": "H1", "drug_code": "PCM", "consumption_rate": 20.0,
             "effective_stock": 0, "at_risk": 0, "reserve": 0, "shortage": 420, "target_days": 21},
            # H2 has excess AMOX
            {"facility_id": "H2", "drug_code": "AMOX", "consumption_rate": 15.0,
             "effective_stock": 510, "at_risk": 290, "reserve": 54, "shortage": 0, "target_days": 21},
            # H3 needs AMOX
            {"facility_id": "H3", "drug_code": "AMOX", "consumption_rate": 8.0,
             "effective_stock": 0, "at_risk": 0, "reserve": 0, "shortage": 168, "target_days": 21},
            # H3 needs ORS
            {"facility_id": "H3", "drug_code": "ORS", "consumption_rate": 5.0,
             "effective_stock": 20, "at_risk": 0, "reserve": 18, "shortage": 85, "target_days": 21},
            # H1 needs IFA
            {"facility_id": "H1", "drug_code": "IFA", "consumption_rate": 10.0,
             "effective_stock": 0, "at_risk": 0, "reserve": 0, "shortage": 210, "target_days": 21},
            # H2 has excess IFA
            {"facility_id": "H2", "drug_code": "IFA", "consumption_rate": 5.0,
             "effective_stock": 195, "at_risk": 2805, "reserve": 18, "shortage": 0, "target_days": 21},
        ],
    }
    return build_snapshot(data, today=today)
