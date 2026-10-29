"""Feasibility rules F1-F6: positive and negative case for each."""
from __future__ import annotations

from datetime import date

import pytest

from app.feasibility import check_feasibility, check_f1_f3_only, BUFFER_DAYS
from app.snapshot import Snapshot, Facility, Drug, Route, Vehicle, Lot, build_snapshot


@pytest.fixture
def snap(today):
    """Minimal snapshot for targeted feasibility tests."""
    data = {
        "facilities": [
            {"id": "SRC", "name": "Source", "type": "DH", "cold_storage": True},
            {"id": "DST", "name": "Dest", "type": "TH", "cold_storage": True},
            {"id": "NO_COLD", "name": "No Cold", "type": "PHC", "cold_storage": False},
        ],
        "drugs": [
            {"code": "DRUG_A", "name": "Drug A", "ven": "E", "unit": "tab", "pack_size": 10,
             "cold_chain": False, "controlled": False, "min_residual_days": 30, "unit_cost_inr": 1.0},
            {"code": "COLD_DRUG", "name": "Cold Drug", "ven": "V", "unit": "vial", "pack_size": 1,
             "cold_chain": True, "controlled": False, "min_residual_days": 60, "unit_cost_inr": 45.0},
            {"code": "CONTROLLED", "name": "Morphine", "ven": "V", "unit": "amp", "pack_size": 5,
             "cold_chain": False, "controlled": True, "min_residual_days": 60, "unit_cost_inr": 35.0},
        ],
        "routes": [
            {"src_facility_id": "SRC", "dst_facility_id": "DST", "distance_km": 10,
             "transit_hours": 0.5, "cold_chain": True, "cost_ambient_inr": 50, "cost_cold_inr": 120},
            {"src_facility_id": "SRC", "dst_facility_id": "NO_COLD", "distance_km": 15,
             "transit_hours": 0.8, "cold_chain": False, "cost_ambient_inr": 70, "cost_cold_inr": 0},
        ],
        "vehicles": [
            {"id": "V1", "name": "Cold Van", "cold_chain": True, "capacity_units": 5000},
        ],
        "lots": [],
        "positions": [],
    }
    return build_snapshot(data, today=today)


# ---------- F1: Drug identity ----------

def test_f1_pass(snap):
    r = check_feasibility("SRC", "DST", "DRUG_A", date(2027, 3, 1), 10, 10, snap)
    assert r.rules["F1"] is True


def test_f1_fail_unknown_drug(snap):
    r = check_feasibility("SRC", "DST", "UNKNOWN", date(2027, 3, 1), 10, 10, snap)
    assert r.rules["F1"] is False
    assert not r.feasible
    assert any(f.rule == "F1" for f in r.failed_rules)


def test_f1_fail_same_facility(snap):
    r = check_feasibility("SRC", "SRC", "DRUG_A", date(2027, 3, 1), 10, 10, snap)
    assert r.rules["F1"] is False


# ---------- F2: Route exists ----------

def test_f2_pass(snap):
    r = check_feasibility("SRC", "DST", "DRUG_A", date(2027, 3, 1), 10, 10, snap)
    assert r.rules["F2"] is True


def test_f2_fail_no_route(snap):
    r = check_feasibility("DST", "NO_COLD", "DRUG_A", date(2027, 3, 1), 10, 10, snap)
    assert r.rules["F2"] is False
    assert any(f.rule == "F2" for f in r.failed_rules)


# ---------- F3: Cold chain ----------

def test_f3_pass_cold_drug_cold_route(snap):
    r = check_feasibility("SRC", "DST", "COLD_DRUG", date(2027, 6, 1), 10, 10, snap)
    assert r.rules["F3"] is True


def test_f3_pass_non_cold_drug(snap):
    r = check_feasibility("SRC", "NO_COLD", "DRUG_A", date(2027, 3, 1), 10, 10, snap)
    assert r.rules["F3"] is True


def test_f3_fail_cold_drug_no_cold_route(snap):
    r = check_feasibility("SRC", "NO_COLD", "COLD_DRUG", date(2027, 6, 1), 10, 10, snap)
    assert r.rules["F3"] is False
    assert any(f.rule == "F3" for f in r.failed_rules)


# ---------- F4: Usable > 0 and residual shelf life ----------

def test_f4_pass_worked_example(snap):
    """50 vials, dst rate 2/day, 14 usable days, no dst stock -> usable 28."""
    # expiry in 15 days, transit ~0.02 days (0.5h), buffer 1 -> ~14 days usable
    expiry = date(2026, 11, 16)
    r = check_feasibility(
        "SRC", "DST", "DRUG_A",
        lot_expiry=expiry,
        chunk_qty=50,
        usable=28,
        snap=snap,
    )
    # residual = 15 - 0.02 - 1 = ~14 days, min_residual=30 -> FAIL
    assert r.rules["F4"] is False

    # Now with longer shelf life (min_residual_days=30 needs >=31 days to expiry)
    expiry_ok = date(2026, 12, 3)  # 32 days from today
    r2 = check_feasibility(
        "SRC", "DST", "DRUG_A",
        lot_expiry=expiry_ok,
        chunk_qty=50,
        usable=28,
        snap=snap,
    )
    assert r2.rules["F4"] is True


def test_f4_fail_usable_zero(snap):
    """Usable=0 at destination -> F4 fails."""
    r = check_feasibility(
        "SRC", "DST", "DRUG_A",
        lot_expiry=date(2027, 6, 1),
        chunk_qty=50,
        usable=0,
        snap=snap,
    )
    assert r.rules["F4"] is False
    assert any("usable=0" in f.detail for f in r.failed_rules if f.rule == "F4")


def test_f4_fail_residual_too_short(snap):
    """Residual shelf life < min_residual_days -> F4 fails."""
    # COLD_DRUG has min_residual_days=60. Expiry 30 days away -> residual ~29 < 60
    expiry = date(2026, 12, 1)  # 30 days from Nov 1
    r = check_feasibility(
        "SRC", "DST", "COLD_DRUG",
        lot_expiry=expiry,
        chunk_qty=10,
        usable=5,
        snap=snap,
    )
    assert r.rules["F4"] is False
    assert any("residual shelf life" in f.detail for f in r.failed_rules if f.rule == "F4")


def test_f4_pass_sufficient_residual(snap):
    """Residual shelf life >= min_residual_days and usable > 0 -> F4 passes."""
    # COLD_DRUG min_residual=60. Expiry 90 days away -> residual ~89 >= 60
    expiry = date(2027, 1, 30)
    r = check_feasibility(
        "SRC", "DST", "COLD_DRUG",
        lot_expiry=expiry,
        chunk_qty=10,
        usable=5,
        snap=snap,
    )
    assert r.rules["F4"] is True


# ---------- F5: Reserve ----------

def test_f5_pass(snap):
    r = check_feasibility(
        "SRC", "DST", "DRUG_A",
        lot_expiry=date(2027, 3, 1),
        chunk_qty=10, usable=10, snap=snap,
        transferable_qty=20,
    )
    assert r.rules["F5"] is True


def test_f5_fail_exceeds_transferable(snap):
    r = check_feasibility(
        "SRC", "DST", "DRUG_A",
        lot_expiry=date(2027, 3, 1),
        chunk_qty=30, usable=10, snap=snap,
        transferable_qty=20,
    )
    assert r.rules["F5"] is False
    assert any(f.rule == "F5" for f in r.failed_rules)


# ---------- F6: Not controlled ----------

def test_f6_pass(snap):
    r = check_feasibility("SRC", "DST", "DRUG_A", date(2027, 3, 1), 10, 10, snap)
    assert r.rules["F6"] is True


def test_f6_fail_controlled(snap):
    r = check_feasibility("SRC", "DST", "CONTROLLED", date(2027, 6, 1), 10, 10, snap)
    assert r.rules["F6"] is False
    assert not r.feasible
    assert any(f.rule == "F6" and "controlled" in f.detail for f in r.failed_rules)


# ---------- Combined: all pass, all fail ----------

def test_all_rules_pass(snap):
    r = check_feasibility(
        "SRC", "DST", "DRUG_A",
        lot_expiry=date(2027, 3, 1),
        chunk_qty=10, usable=10, snap=snap,
        transferable_qty=20,
    )
    assert r.feasible
    assert all(r.rules.values())
    assert len(r.failed_rules) == 0


def test_multiple_failures(snap):
    """Unknown drug + no route -> multiple failures."""
    r = check_feasibility(
        "NO_COLD", "SRC", "UNKNOWN",
        lot_expiry=date(2027, 3, 1),
        chunk_qty=10, usable=0, snap=snap,
    )
    assert not r.feasible
    assert len(r.failed_rules) >= 2
