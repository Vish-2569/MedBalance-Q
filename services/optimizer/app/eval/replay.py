"""28-day replay simulator for MedBalance-Q evaluation.

In-process, no containers. Reuses the same FEFO, feasibility, forecast,
and solver code as the live optimizer. Produces JSON reports + charts.

Usage:
    python -m app.eval.replay --seeds 20 --days 28 --policies A,B,C,D,E
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# ── Resolve paths before importing optimizer modules ────────────────
SERVICE_DIR = Path(__file__).resolve().parents[2]  # services/optimizer
REPO_ROOT = SERVICE_DIR.parents[1]                 # repo root

# Ensure imports work when run as `python -m app.eval.replay` from services/optimizer
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))
LIB_DIR = REPO_ROOT / "libs" / "medbal_common"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import yaml

from app.snapshot import Snapshot, Facility, Drug, Route, Vehicle, Lot, Position, Policy, build_snapshot
from app.positions import compute_all_positions
from app.candidates import generate_candidates
from app.baselines import greedy_f4, greedy_phone_call, TransferOrder
from app.qubo_builder import build_qubo, QUBOConfig
from app.solvers.chain import solve_chain
from app.solvers.greedy_descent import GreedyDescent
from app.validator import apply_plan
from app.metrics import compute_metrics
from app.milp import solve_milp

# ── Seed data constants (mirror generate.py) ───────────────────────

DEMAND: dict[str, dict[str, int]] = {
    "PCM":         {"DH": 40, "TH": 25, "CHC": 15, "PHC": 8},
    "AMOX":        {"DH": 20, "TH": 12, "CHC": 8,  "PHC": 4},
    "METFORMIN":   {"DH": 15, "TH": 10, "CHC": 5,  "PHC": 3},
    "AMLODIPINE":  {"DH": 12, "TH": 8,  "CHC": 4,  "PHC": 2},
    "IFA":         {"DH": 25, "TH": 15, "CHC": 10, "PHC": 5},
    "ORS":         {"DH": 10, "TH": 8,  "CHC": 6,  "PHC": 3},
    "INSULIN":     {"DH": 3,  "TH": 2,  "CHC": 1,  "PHC": 0},
    "OXYTOCIN":    {"DH": 4,  "TH": 2,  "CHC": 1,  "PHC": 0},
    "CEFTRIAXONE": {"DH": 5,  "TH": 3,  "CHC": 2,  "PHC": 1},
    "RL":          {"DH": 6,  "TH": 4,  "CHC": 2,  "PHC": 1},
    "TD":          {"DH": 8,  "TH": 5,  "CHC": 3,  "PHC": 2},
    "ASV":         {"DH": 1,  "TH": 0,  "CHC": 0,  "PHC": 0},
    "MORPHINE":    {"DH": 1,  "TH": 0,  "CHC": 0,  "PHC": 0},
}

POLICY_BY_LEVEL: dict[str, dict[str, int]] = {
    "DH":  {"min_reserve_days": 7, "target_days": 21, "lead_time_days": 3},
    "TH":  {"min_reserve_days": 7, "target_days": 21, "lead_time_days": 3},
    "CHC": {"min_reserve_days": 5, "target_days": 14, "lead_time_days": 4},
    "PHC": {"min_reserve_days": 3, "target_days": 10, "lead_time_days": 5},
}

STORY_LOTS = [
    ("H1", "INSULIN",     "B-INS-H1-001", "2026-11-15",   5),
    ("H1", "OXYTOCIN",    "B-OXY-H1-001", "2026-11-20",   3),
    ("H1", "PCM",         "B-PCM-H1-001", "2027-04-15", 800),
    ("H1", "AMOX",        "B-AMX-H1-001", "2027-03-20", 400),
    ("H1", "CEFTRIAXONE", "B-CFT-H1-001", "2027-02-28", 100),
    ("H1", "METFORMIN",   "B-MET-H1-001", "2027-05-01", 300),
    ("H1", "AMLODIPINE",  "B-AML-H1-001", "2027-04-15", 200),
    ("H1", "IFA",         "B-IFA-H1-001", "2027-03-01", 500),
    ("H1", "RL",          "B-RL-H1-001",  "2027-06-01", 100),
    ("H2", "IFA",         "B-IFA-H2-001", "2026-12-10", 3000),
    ("H2", "PCM",         "B-PCM-H2-001", "2026-11-25", 1500),
    ("H2", "AMOX",        "B-AMX-H2-001", "2026-12-05",  800),
    ("H2", "METFORMIN",   "B-MET-H2-001", "2027-06-30",  200),
    ("H2", "MORPHINE",    "B-MOR-H2-001", "2027-08-15",   15),
    ("H2", "OXYTOCIN",    "B-OXY-H2-001", "2027-04-01",   40),
    ("H2", "CEFTRIAXONE", "B-CFT-H2-001", "2027-05-01",   60),
    ("H2", "INSULIN",     "B-INS-H2-001", "2027-03-01",   30),
    ("H3", "ORS",         "B-ORS-H3-001", "2027-01-15",   20),
    ("H3", "PCM",         "B-PCM-H3-001", "2027-05-01",  200),
    ("H3", "TD",          "B-TD-H3-001",  "2027-09-01",   50),
    ("H3", "AMOX",        "B-AMX-H3-001", "2027-03-15",   80),
    ("H3", "RL",          "B-RL-H3-001",  "2027-04-01",   30),
    ("H3", "METFORMIN",   "B-MET-H3-001", "2027-06-01",   50),
    ("H4", "INSULIN",     "B-INS-H4-001", "2026-11-19",   50),
    ("H4", "PCM",         "B-PCM-H4-001", "2027-03-01",   60),
    ("H4", "ORS",         "B-ORS-H4-001", "2027-02-15",   30),
    ("H4", "AMLODIPINE",  "B-AML-H4-001", "2027-07-01",   40),
    ("H4", "AMOX",        "B-AMX-H4-001", "2027-02-01",   20),
    ("W0", "INSULIN",     "B-INS-W0-001", "2027-06-30",  200),
    ("W0", "OXYTOCIN",    "B-OXY-W0-001", "2027-05-15",  100),
    ("W0", "PCM",         "B-PCM-W0-001", "2027-08-01", 5000),
    ("W0", "AMOX",        "B-AMX-W0-001", "2027-07-01", 2000),
    ("W0", "ORS",         "B-ORS-W0-001", "2027-04-01", 3000),
    ("W0", "CEFTRIAXONE", "B-CFT-W0-001", "2027-09-01",  500),
    ("W0", "RL",          "B-RL-W0-001",  "2028-01-01", 1000),
    ("W0", "TD",          "B-TD-W0-001",  "2027-12-01",  500),
    ("W0", "ASV",         "B-ASV-W0-001", "2027-10-01",   30),
    ("W0", "IFA",         "B-IFA-W0-001", "2027-11-01", 10000),
    ("W0", "METFORMIN",   "B-MET-W0-001", "2027-08-01", 3000),
    ("W0", "AMLODIPINE",  "B-AML-W0-001", "2027-09-01", 2000),
    ("W0", "MORPHINE",    "B-MOR-W0-001", "2027-07-01",   50),
]

SIM_START_DATE = date(2026, 11, 1)


# ── Scenario events ─────────────────────────────────────────────────

SCENARIO_EVENTS: list[dict[str, Any]] = [
    {"day": 9,  "type": "bad_data",       "facility": "H4"},
    {"day": 18, "type": "fridge_failure",  "vehicle": "CV-02"},
    {"day": 15, "type": "dengue_outbreak", "facility": "H3", "duration": 7,
     "drugs_affected": ["ORS", "PCM", "RL"], "multiplier": 2.5},
]


# ── Pure-Python Poisson (same as generate.py) ──────────────────────

def poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p < L:
            return k - 1


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ── Build initial snapshot from seed YAML ───────────────────────────

def load_seed_data() -> dict[str, Any]:
    """Load district.yaml and drugs.yaml, build snapshot dict."""
    seed_dir = REPO_ROOT / "data" / "seed"
    with open(seed_dir / "district.yaml", encoding="utf-8") as f:
        district = yaml.safe_load(f)
    with open(seed_dir / "drugs.yaml", encoding="utf-8") as f:
        drugs_data = yaml.safe_load(f)

    facilities = district["facilities"]
    drugs = drugs_data["drugs"]
    vehicles = district["vehicles"]
    fac_by_id = {f["id"]: f for f in facilities}

    routes = []
    for a in facilities:
        for b in facilities:
            if a["id"] == b["id"]:
                continue
            dist = haversine(a["lat"], a["lon"], b["lat"], b["lon"]) * 1.3
            transit_h = max(0.5, dist / 40.0)
            cold_ok = a["cold_storage_ok"] and b["cold_storage_ok"]
            routes.append({
                "src_facility_id": a["id"],
                "dst_facility_id": b["id"],
                "distance_km": round(dist, 2),
                "transit_hours": round(transit_h, 2),
                "cold_chain": cold_ok,
                "cost_ambient_inr": round(8.0 * dist, 2),
                "cost_cold_inr": round(15.0 * dist, 2),
            })

    lots = []
    for fac_id, drug_code, batch_no, expiry, qty in STORY_LOTS:
        lots.append({
            "facility_id": fac_id,
            "drug_code": drug_code,
            "batch_no": batch_no,
            "expiry": expiry,
            "qty": qty,
        })

    policies = []
    for f in facilities:
        if f["level"] == "WH":
            continue
        pol = POLICY_BY_LEVEL.get(f["level"], POLICY_BY_LEVEL["PHC"])
        for d in drugs:
            policies.append({
                "facility_id": f["id"],
                "drug_code": d["code"],
                "min_reserve_days": pol["min_reserve_days"],
                "target_days": pol["target_days"],
                "lead_time_days": pol["lead_time_days"],
            })

    fac_data = []
    for f in facilities:
        fac_data.append({
            "id": f["id"],
            "name": f["name"],
            "level": f["level"],
            "cold_storage": f["cold_storage_ok"],
        })

    drug_data = []
    for d in drugs:
        drug_data.append({
            "code": d["code"],
            "name": d["name"],
            "ven": d["ven"],
            "unit": d["unit"],
            "pack_size": d["pack_size"],
            "cold_chain": d["cold_chain"],
            "controlled": d["controlled"],
            "min_residual_days": d["min_residual_days"],
            "unit_cost_inr": d["unit_cost_inr"],
        })

    vehicle_data = []
    for v in vehicles:
        vehicle_data.append({
            "id": v["id"],
            "name": v["name"],
            "cold_chain": v["cold_chain"],
            "capacity_units": v["capacity_units"],
        })

    return {
        "facilities": fac_data,
        "drugs": drug_data,
        "routes": routes,
        "vehicles": vehicle_data,
        "lots": lots,
        "policies": policies,
        "positions": [],
    }


# ── Day metrics ─────────────────────────────────────────────────────

@dataclass
class DayLog:
    day: int
    sim_date: str
    consumed: dict[tuple[str, str], int] = field(default_factory=dict)
    expired_units: int = 0
    expired_inr: float = 0.0
    stockout_pairs: int = 0
    stockout_pairs_ven_weighted: float = 0.0
    unmet_demand: int = 0
    transfers_planned: int = 0
    waste_moved: int = 0
    violations: int = 0
    reserve_breaches: int = 0
    trips: int = 0
    km: float = 0.0
    cost_inr: float = 0.0
    solve_time_ms: float = 0.0
    solver_tier: str = ""


@dataclass
class RunResult:
    seed: int
    policy: str
    days: int
    stockout_days: int = 0
    stockout_days_ven: float = 0.0
    unmet_demand: int = 0
    expired_units: int = 0
    expired_inr: float = 0.0
    waste_moved: int = 0
    violations: int = 0
    reserve_breaches: int = 0
    trips: int = 0
    km: float = 0.0
    cost_inr: float = 0.0
    solve_times: list[float] = field(default_factory=list)
    solver_tiers: list[str] = field(default_factory=list)
    day_logs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "policy": self.policy,
            "days": self.days,
            "stockout_days": self.stockout_days,
            "stockout_days_ven_weighted": round(self.stockout_days_ven, 2),
            "unmet_demand": self.unmet_demand,
            "expired_units": self.expired_units,
            "expired_inr": round(self.expired_inr, 2),
            "waste_moved": self.waste_moved,
            "violations": self.violations,
            "reserve_breaches": self.reserve_breaches,
            "trips": self.trips,
            "km": round(self.km, 1),
            "cost_inr": round(self.cost_inr, 2),
            "avg_solve_time_ms": round(statistics.mean(self.solve_times), 1) if self.solve_times else 0,
            "solver_tiers": list(set(self.solver_tiers)),
        }


# ── Snapshot mutation helpers ───────────────────────────────────────

def _rebuild_lots_list(snap: Snapshot) -> None:
    """Rebuild snap.lots from snap.lots_by_fd."""
    snap.lots = []
    for lots in snap.lots_by_fd.values():
        snap.lots.extend(lots)


def _rebuild_positions(snap: Snapshot) -> None:
    """Recompute positions from current lots and store into snap.positions."""
    from medbal_common.fefo import compute_position
    for (fac_id, drug_code), lots in snap.lots_by_fd.items():
        pol = snap.policies.get((fac_id, drug_code))
        old_pos = snap.positions.get((fac_id, drug_code))
        rate = old_pos.rate if old_pos else 0.0
        target = pol.target_days if pol else (old_pos.target_days if old_pos else 21)
        min_res = pol.min_reserve_days if pol else 7
        lead = pol.lead_time_days if pol else 3

        lot_dicts = [{"batch_no": l.batch_no, "expiry": l.expiry, "qty": l.qty} for l in lots]
        result = compute_position(
            facility_id=fac_id, drug_code=drug_code, lots=lot_dicts,
            rate=rate, today=snap.today,
            min_reserve_days=min_res, target_days=target, lead_time_days=lead,
        )
        snap.positions[(fac_id, drug_code)] = Position(
            facility_id=fac_id, drug_code=drug_code,
            effective_stock=result.effective_stock, at_risk=result.at_risk,
            reserve=result.reserve, shortage=result.shortage,
            rate=rate, target_days=target,
        )


def _deep_copy_snap(snap: Snapshot) -> Snapshot:
    new = Snapshot(today=snap.today)
    new.facilities = dict(snap.facilities)
    new.drugs = dict(snap.drugs)
    new.routes = dict(snap.routes)
    new.vehicles = list(snap.vehicles)
    new.lots_by_fd = {k: list(v) for k, v in snap.lots_by_fd.items()}
    new.lots = list(snap.lots)
    new.positions = {k: copy.copy(v) for k, v in snap.positions.items()}
    new.policies = dict(snap.policies)
    return new


# ── Core simulation ─────────────────────────────────────────────────

def _compute_demand_rates(snap: Snapshot) -> dict[tuple[str, str], float]:
    """Get base demand rate for each (facility, drug) from DEMAND table."""
    rates: dict[tuple[str, str], float] = {}
    for fac_id, fac in snap.facilities.items():
        level = fac.level
        if level == "WH":
            continue
        for drug_code in snap.drugs:
            base = DEMAND.get(drug_code, {}).get(level, 0)
            if base > 0:
                rates[(fac_id, drug_code)] = float(base)
    return rates


def _set_rates_on_snap(snap: Snapshot, rates: dict[tuple[str, str], float]) -> None:
    """Inject consumption rates into snap.positions."""
    for (fac_id, drug_code), rate in rates.items():
        pos = snap.positions.get((fac_id, drug_code))
        if pos:
            pos.rate = rate
        else:
            pol = snap.policies.get((fac_id, drug_code))
            target = pol.target_days if pol else 21
            snap.positions[(fac_id, drug_code)] = Position(
                facility_id=fac_id, drug_code=drug_code,
                effective_stock=0, at_risk=0, reserve=0, shortage=0,
                rate=rate, target_days=target,
            )


def _get_demand_multiplier(
    day: int, fac_id: str, drug_code: str, scenarios: list[dict],
) -> float:
    """Scenario-driven demand multiplier."""
    mult = 1.0
    for ev in scenarios:
        if ev["type"] == "dengue_outbreak":
            start = ev["day"]
            end = start + ev.get("duration", 7)
            if start <= day < end:
                if fac_id == ev.get("facility") or ev.get("facility") is None:
                    if drug_code in ev.get("drugs_affected", []):
                        mult = max(mult, ev["multiplier"])
    return mult


def _is_bad_data_day(day: int, fac_id: str, scenarios: list[dict]) -> bool:
    for ev in scenarios:
        if ev["type"] == "bad_data" and ev["day"] == day and ev.get("facility") == fac_id:
            return True
    return False


def _is_fridge_failure_active(day: int, scenarios: list[dict]) -> str | None:
    """Returns vehicle ID affected by fridge failure, or None."""
    for ev in scenarios:
        if ev["type"] == "fridge_failure" and day >= ev["day"]:
            return ev.get("vehicle")
    return None


def run_single(
    seed: int,
    policy: str,
    n_days: int = 28,
    solver_override: str | None = None,
    qubo_config: QUBOConfig | None = None,
) -> RunResult:
    """Run one replay: seed determines demand randomness."""
    rng = random.Random(seed)
    seed_data = load_seed_data()
    snap = build_snapshot(seed_data, today=SIM_START_DATE)

    base_rates = _compute_demand_rates(snap)
    _set_rates_on_snap(snap, base_rates)
    _rebuild_positions(snap)

    result = RunResult(seed=seed, policy=policy, days=n_days)
    in_transit: list[dict[str, Any]] = []
    planning_days_of_week = {0, 3}  # Monday and Thursday

    # Track initial stock for conservation invariant
    initial_stock: dict[tuple[str, str], int] = {}
    for (fac_id, dc), lots in snap.lots_by_fd.items():
        initial_stock[(fac_id, dc)] = sum(l.qty for l in lots)

    total_consumed: dict[tuple[str, str], int] = {}
    total_expired: dict[tuple[str, str], int] = {}
    total_received: dict[tuple[str, str], int] = {}
    total_in_transit: dict[tuple[str, str], int] = {}

    for day_idx in range(n_days):
        today = SIM_START_DATE + timedelta(days=day_idx)
        snap.today = today
        day_log = DayLog(day=day_idx, sim_date=today.isoformat())

        # ── 1. Deliver arrivals ──────────────────────────────────
        still_in_transit = []
        for shipment in in_transit:
            if today >= shipment["arrival_date"]:
                dst_key = (shipment["dst"], shipment["drug_code"])
                dst_lots = snap.lots_by_fd.get(dst_key, [])
                existing = None
                for lot in dst_lots:
                    if lot.batch_no == shipment["batch_no"]:
                        existing = lot
                        break
                if existing:
                    new_lots = []
                    for lot in dst_lots:
                        if lot.batch_no == shipment["batch_no"]:
                            new_lots.append(Lot(
                                facility_id=lot.facility_id,
                                drug_code=lot.drug_code,
                                batch_no=lot.batch_no,
                                expiry=lot.expiry,
                                qty=lot.qty + shipment["qty"],
                            ))
                        else:
                            new_lots.append(lot)
                    snap.lots_by_fd[dst_key] = new_lots
                else:
                    new_lot = Lot(
                        facility_id=shipment["dst"],
                        drug_code=shipment["drug_code"],
                        batch_no=shipment["batch_no"],
                        expiry=date.fromisoformat(shipment["expiry"]),
                        qty=shipment["qty"],
                    )
                    snap.lots_by_fd.setdefault(dst_key, []).append(new_lot)
                total_received[dst_key] = total_received.get(dst_key, 0) + shipment["qty"]
            else:
                still_in_transit.append(shipment)
        in_transit = still_in_transit

        # ── 2. Dispense (FEFO) with Poisson demand ──────────────
        weekday = today.weekday()
        wk_factor = 1.0 if weekday < 5 else (0.6 if weekday == 5 else 0.3)

        for (fac_id, drug_code), base_rate in base_rates.items():
            mult = _get_demand_multiplier(day_idx, fac_id, drug_code, SCENARIO_EVENTS)
            lam = base_rate * wk_factor * mult
            demand = poisson(rng, lam)
            if demand <= 0:
                continue

            # Bad data day at H4: demand is real but the *report* is garbled.
            # We filter bad data from ingestion, so no stock effect — demand continues normally.

            # FEFO dispensing
            lots = snap.lots_by_fd.get((fac_id, drug_code), [])
            lots_sorted = sorted(lots, key=lambda l: l.expiry)
            remaining = demand
            new_lots = []
            dispensed = 0
            for lot in lots_sorted:
                if remaining <= 0:
                    new_lots.append(lot)
                    continue
                take = min(lot.qty, remaining)
                remaining -= take
                dispensed += take
                if lot.qty - take > 0:
                    new_lots.append(Lot(
                        facility_id=lot.facility_id, drug_code=lot.drug_code,
                        batch_no=lot.batch_no, expiry=lot.expiry, qty=lot.qty - take,
                    ))
            snap.lots_by_fd[(fac_id, drug_code)] = new_lots

            total_consumed[(fac_id, drug_code)] = total_consumed.get((fac_id, drug_code), 0) + dispensed
            day_log.consumed[(fac_id, drug_code)] = dispensed
            if remaining > 0:
                day_log.unmet_demand += remaining
                result.unmet_demand += remaining

        # ── 3. Expire lots ──────────────────────────────────────
        for key in list(snap.lots_by_fd.keys()):
            lots = snap.lots_by_fd[key]
            kept = []
            for lot in lots:
                if lot.expiry <= today:
                    day_log.expired_units += lot.qty
                    drug = snap.drugs.get(lot.drug_code)
                    cost = drug.unit_cost_inr if drug else 0
                    day_log.expired_inr += lot.qty * cost
                    result.expired_units += lot.qty
                    result.expired_inr += lot.qty * cost
                    total_expired[key] = total_expired.get(key, 0) + lot.qty
                else:
                    kept.append(lot)
            snap.lots_by_fd[key] = kept

        # ── 4. Fridge failure: remove cold vehicle ──────────────
        failed_vehicle = _is_fridge_failure_active(day_idx, SCENARIO_EVENTS)
        if failed_vehicle:
            snap.vehicles = [v for v in snap.vehicles if v.id != failed_vehicle]

        # ── 5. Rebuild lots list and positions ──────────────────
        _rebuild_lots_list(snap)
        _set_rates_on_snap(snap, base_rates)
        _rebuild_positions(snap)

        # ── 6. Count stockout-days ──────────────────────────────
        for (fac_id, drug_code), pos in snap.positions.items():
            if fac_id in snap.facilities and snap.facilities[fac_id].level == "WH":
                continue
            total_stock = sum(l.qty for l in snap.lots_by_fd.get((fac_id, drug_code), []))
            if total_stock == 0 and base_rates.get((fac_id, drug_code), 0) > 0:
                day_log.stockout_pairs += 1
                drug = snap.drugs.get(drug_code)
                ven_wt = drug.ven_priority if drug else 1
                day_log.stockout_pairs_ven_weighted += ven_wt

        result.stockout_days += day_log.stockout_pairs
        result.stockout_days_ven += day_log.stockout_pairs_ven_weighted

        # ── 7. Plan on planning days ────────────────────────────
        if weekday in planning_days_of_week and policy != "A":
            t0 = time.perf_counter()
            orders, solver_tier, violations = _run_policy(
                snap, policy, solver_override, qubo_config,
            )
            solve_ms = (time.perf_counter() - t0) * 1000

            day_log.solve_time_ms = solve_ms
            day_log.solver_tier = solver_tier
            day_log.violations = violations
            result.violations += violations
            result.solve_times.append(solve_ms)
            if solver_tier:
                result.solver_tiers.append(solver_tier)

            # Dispatch orders → in-transit
            for o in orders:
                route = snap.routes.get((o.src_facility_id, o.dst_facility_id))
                transit_d = int(math.ceil(route.transit_days)) if route else 1
                arrival = today + timedelta(days=transit_d)

                # Decrement source
                src_key = (o.src_facility_id, o.drug_code)
                src_lots = snap.lots_by_fd.get(src_key, [])
                new_src = []
                qty_left = o.qty
                for lot in src_lots:
                    if lot.batch_no == o.batch_no and qty_left > 0:
                        take = min(lot.qty, qty_left)
                        qty_left -= take
                        if lot.qty - take > 0:
                            new_src.append(Lot(
                                facility_id=lot.facility_id, drug_code=lot.drug_code,
                                batch_no=lot.batch_no, expiry=lot.expiry, qty=lot.qty - take,
                            ))
                    else:
                        new_src.append(lot)
                snap.lots_by_fd[src_key] = new_src

                # Find expiry for the lot
                expiry_str = today.isoformat()
                for lot in src_lots:
                    if lot.batch_no == o.batch_no:
                        expiry_str = lot.expiry.isoformat()
                        break

                in_transit.append({
                    "dst": o.dst_facility_id,
                    "drug_code": o.drug_code,
                    "batch_no": o.batch_no,
                    "qty": o.qty,
                    "expiry": expiry_str,
                    "arrival_date": arrival,
                })

                day_log.transfers_planned += 1
                day_log.waste_moved += o.usable
                result.waste_moved += o.usable

                if route:
                    day_log.trips += 1
                    day_log.km += route.distance_km
                    drug = snap.drugs.get(o.drug_code)
                    if drug and drug.cold_chain:
                        day_log.cost_inr += route.cost_cold_inr
                    else:
                        day_log.cost_inr += route.cost_ambient_inr

            result.trips += day_log.trips
            result.km += day_log.km
            result.cost_inr += day_log.cost_inr

            # Rebuild after dispatch
            _rebuild_lots_list(snap)
            _rebuild_positions(snap)

        # ── 8. Reserve breach check ─────────────────────────────
        positions = compute_all_positions(snap)
        for (fac_id, dc), pr in positions.items():
            total_stock = sum(l.qty for l in snap.lots_by_fd.get((fac_id, dc), []))
            if total_stock < pr.reserve and total_stock > 0:
                day_log.reserve_breaches += 1
                result.reserve_breaches += 1

        result.day_logs.append({
            "day": day_log.day,
            "date": day_log.sim_date,
            "stockout_pairs": day_log.stockout_pairs,
            "expired_units": day_log.expired_units,
            "unmet_demand": day_log.unmet_demand,
            "transfers": day_log.transfers_planned,
            "violations": day_log.violations,
            "solve_time_ms": round(day_log.solve_time_ms, 1),
        })

    return result


def _run_policy(
    snap: Snapshot,
    policy: str,
    solver_override: str | None,
    qubo_config: QUBOConfig | None,
) -> tuple[list[TransferOrder], str, int]:
    """Run the specified policy's solver. Returns (orders, tier_name, violations)."""
    if policy == "A":
        return [], "none", 0

    if policy == "B":
        orders = greedy_phone_call(snap)
        return orders, "greedy-phone-call", 0

    if policy == "C":
        orders = greedy_f4(snap)
        return orders, "greedy-f4", 0

    if policy in ("D", "D-noF4", "D-noForecast", "D-noGamma"):
        config = qubo_config or QUBOConfig()

        if policy == "D-noGamma":
            config = QUBOConfig(p1=config.p1, p2=config.p2, p3=config.p3, gamma=0.0)

        positions = compute_all_positions(snap)

        if policy == "D-noF4":
            # Ablation: usable = qty (skip usable computation — treat all as usable)
            from app.candidates import Candidate, Chunk, split_chunks, compute_usable
            from app.feasibility import check_feasibility, FeasibilityResult, FailedRule
            cands = generate_candidates(snap, positions)
            for c in cands:
                if c.feasibility.feasible:
                    c.usable = c.chunk.qty
        else:
            cands = generate_candidates(snap, positions)

        if policy == "D-noForecast":
            # Ablation: set all rates to base (no scenario multiplier effect on positions)
            pass  # rates are already base — forecast multiplier not applied in replay

        ven_priority = {code: d.ven_priority for code, d in snap.drugs.items()}
        shortages = {
            (f, d): p.shortage for (f, d), p in snap.positions.items() if p.shortage > 0
        }

        qubo_result = build_qubo(cands, ven_priority, shortages, config)
        if qubo_result.num_variables == 0:
            return [], "qubo-empty", 0

        if solver_override == "local":
            tiers = [GreedyDescent(restarts=8, seed=42)]
        else:
            tiers = None

        solve_result = solve_chain(
            qubo_result.Q, qubo_result.offset, qubo_result.num_variables,
            top_k=1, timeout=3.0, tiers=tiers,
        )

        if not solve_result.samples:
            orders = greedy_f4(snap)
            return orders, f"qubo-fallback-{solve_result.tier}", 0

        best = solve_result.samples[0]
        selected_pairs = []
        for var_idx, val in best.x.items():
            if val == 1 and var_idx < len(qubo_result.variables):
                ci = qubo_result.variables[var_idx]
                selected_pairs.append((ci, cands[ci]))

        val_result = apply_plan(snap, selected_pairs)

        orders = []
        for vo in val_result.orders:
            if vo.dropped:
                continue
            drug = snap.drugs.get(vo.drug_code)
            orders.append(TransferOrder(
                id=f"ORD-R-{len(orders)+1:03d}",
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

        return orders, solve_result.tier, len(val_result.violations)

    if policy == "E":
        positions = compute_all_positions(snap)
        cands = generate_candidates(snap, positions)
        ven_priority = {code: d.ven_priority for code, d in snap.drugs.items()}
        shortages = {
            (f, d): p.shortage for (f, d), p in snap.positions.items() if p.shortage > 0
        }
        qubo_result = build_qubo(cands, ven_priority, shortages)
        milp_result = solve_milp(
            cands, ven_priority, shortages, qubo_result.norm_factor,
            time_limit_s=20.0,
        )
        orders = []
        for ci in milp_result.selected_indices:
            c = cands[ci]
            drug = snap.drugs.get(c.drug_code)
            orders.append(TransferOrder(
                id=f"ORD-M-{len(orders)+1:03d}",
                src_facility_id=c.chunk.lot.facility_id,
                dst_facility_id=c.destination_id,
                drug_code=c.drug_code,
                drug_name=drug.name if drug else c.drug_code,
                batch_no=c.chunk.lot.batch_no,
                qty=c.chunk.qty,
                usable=c.usable,
                score=round(milp_result.objective, 4),
                temperature_req="cold_chain" if (drug and drug.cold_chain) else "ambient",
            ))
        return orders, f"milp-{milp_result.status}", 0

    return [], "unknown", 0


# ── Aggregation ─────────────────────────────────────────────────────

@dataclass
class AggregatedResult:
    policy: str
    n_seeds: int
    stockout_days_mean: float = 0
    stockout_days_std: float = 0
    stockout_days_ci95: tuple[float, float] = (0, 0)
    stockout_ven_mean: float = 0
    unmet_demand_mean: float = 0
    expired_units_mean: float = 0
    expired_inr_mean: float = 0
    waste_moved_mean: float = 0
    violations_mean: float = 0
    reserve_breaches_mean: float = 0
    trips_mean: float = 0
    km_mean: float = 0
    cost_inr_mean: float = 0
    avg_solve_ms: float = 0
    solver_tiers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "n_seeds": self.n_seeds,
            "stockout_days": {"mean": round(self.stockout_days_mean, 1), "std": round(self.stockout_days_std, 1),
                              "ci95_lo": round(self.stockout_days_ci95[0], 1), "ci95_hi": round(self.stockout_days_ci95[1], 1)},
            "stockout_ven_weighted_mean": round(self.stockout_ven_mean, 1),
            "unmet_demand_mean": round(self.unmet_demand_mean, 1),
            "expired_units_mean": round(self.expired_units_mean, 1),
            "expired_inr_mean": round(self.expired_inr_mean, 2),
            "waste_moved_mean": round(self.waste_moved_mean, 1),
            "violations_mean": round(self.violations_mean, 2),
            "reserve_breaches_mean": round(self.reserve_breaches_mean, 1),
            "trips_mean": round(self.trips_mean, 1),
            "km_mean": round(self.km_mean, 1),
            "cost_inr_mean": round(self.cost_inr_mean, 2),
            "avg_solve_ms": round(self.avg_solve_ms, 1),
            "solver_tiers": self.solver_tiers,
        }


def aggregate(runs: list[RunResult]) -> AggregatedResult:
    n = len(runs)
    if n == 0:
        return AggregatedResult(policy="?", n_seeds=0)

    policy = runs[0].policy
    vals = [r.stockout_days for r in runs]
    mean_sd = statistics.mean(vals)
    std_sd = statistics.stdev(vals) if n > 1 else 0
    se = std_sd / math.sqrt(n) if n > 1 else 0
    ci_lo = mean_sd - 1.96 * se
    ci_hi = mean_sd + 1.96 * se

    all_tiers: set[str] = set()
    all_solve: list[float] = []
    for r in runs:
        all_tiers.update(r.solver_tiers)
        all_solve.extend(r.solve_times)

    return AggregatedResult(
        policy=policy,
        n_seeds=n,
        stockout_days_mean=mean_sd,
        stockout_days_std=std_sd,
        stockout_days_ci95=(ci_lo, ci_hi),
        stockout_ven_mean=statistics.mean([r.stockout_days_ven for r in runs]),
        unmet_demand_mean=statistics.mean([r.unmet_demand for r in runs]),
        expired_units_mean=statistics.mean([r.expired_units for r in runs]),
        expired_inr_mean=statistics.mean([r.expired_inr for r in runs]),
        waste_moved_mean=statistics.mean([r.waste_moved for r in runs]),
        violations_mean=statistics.mean([r.violations for r in runs]),
        reserve_breaches_mean=statistics.mean([r.reserve_breaches for r in runs]),
        trips_mean=statistics.mean([r.trips for r in runs]),
        km_mean=statistics.mean([r.km for r in runs]),
        cost_inr_mean=statistics.mean([r.cost_inr for r in runs]),
        avg_solve_ms=statistics.mean(all_solve) if all_solve else 0,
        solver_tiers=sorted(all_tiers),
    )


# ── Charts (optional — matplotlib) ─────────────────────────────────

def generate_charts(agg_results: list[AggregatedResult], out_dir: Path) -> list[str]:
    """Generate PNG charts. Returns list of created file paths."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib not installed - skipping charts")
        return []

    created: list[str] = []
    policies = [a.policy for a in agg_results]
    x = range(len(policies))

    # 1. Stockout days comparison
    fig, ax = plt.subplots(figsize=(8, 5))
    vals = [a.stockout_days_mean for a in agg_results]
    errs = [a.stockout_days_std for a in agg_results]
    bars = ax.bar(x, vals, yerr=errs, capsize=4, color=["#94a3b8", "#f59e0b", "#3b82f6", "#14b8a6", "#10b981"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(policies)
    ax.set_ylabel("Stockout-Days (28d)")
    ax.set_title("Stockout-Days by Policy (mean ± std)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = out_dir / "stockout_days.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    created.append(str(path))

    # 2. Expired value
    fig, ax = plt.subplots(figsize=(8, 5))
    vals = [a.expired_inr_mean for a in agg_results]
    ax.bar(x, vals, color=["#94a3b8", "#f59e0b", "#3b82f6", "#14b8a6", "#10b981"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(policies)
    ax.set_ylabel("Expired Value (₹)")
    ax.set_title("Drug Wastage by Policy (mean over seeds)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    path = out_dir / "expired_value.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    created.append(str(path))

    # 3. Cost vs benefit scatter
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ["#94a3b8", "#f59e0b", "#3b82f6", "#14b8a6", "#10b981"]
    for i, a in enumerate(agg_results):
        ax.scatter(a.cost_inr_mean, a.stockout_days_mean, s=120, c=colors[i], label=a.policy, zorder=5)
    ax.set_xlabel("Transport Cost (₹)")
    ax.set_ylabel("Stockout-Days")
    ax.set_title("Cost–Benefit Frontier")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = out_dir / "cost_benefit.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    created.append(str(path))

    return created


# ── Markdown summary ────────────────────────────────────────────────

def markdown_summary(agg_results: list[AggregatedResult], ablation_results: list[AggregatedResult]) -> str:
    lines = ["## Replay Evaluation Summary", ""]

    lines.append("| Policy | Stockout-Days | VEN-Wtd | Unmet | Expired ₹ | Waste Moved | Violations | Trips | Cost ₹ | Solve ms |")
    lines.append("|--------|--------------|---------|-------|-----------|-------------|------------|-------|--------|----------|")
    for a in agg_results:
        ci = f"{a.stockout_days_ci95[0]:.0f}–{a.stockout_days_ci95[1]:.0f}"
        lines.append(
            f"| {a.policy} | {a.stockout_days_mean:.1f} ± {a.stockout_days_std:.1f} ({ci}) "
            f"| {a.stockout_ven_mean:.1f} | {a.unmet_demand_mean:.0f} "
            f"| {a.expired_inr_mean:,.0f} | {a.waste_moved_mean:.0f} "
            f"| {a.violations_mean:.1f} | {a.trips_mean:.1f} "
            f"| {a.cost_inr_mean:,.0f} | {a.avg_solve_ms:.0f} |"
        )

    if ablation_results:
        lines.append("")
        lines.append("### Ablation (variants of D)")
        lines.append("| Variant | Stockout-Days | Expired ₹ | Violations |")
        lines.append("|---------|--------------|-----------|------------|")
        for a in ablation_results:
            lines.append(f"| {a.policy} | {a.stockout_days_mean:.1f} ± {a.stockout_days_std:.1f} "
                         f"| {a.expired_inr_mean:,.0f} | {a.violations_mean:.1f} |")

    return "\n".join(lines)


# ── CLI entrypoint ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MedBalance-Q replay evaluation")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--days", type=int, default=28)
    parser.add_argument("--policies", type=str, default="A,B,C,D,E")
    parser.add_argument("--solver", type=str, default="local", help="Solver override for QUBO (local|chain)")
    parser.add_argument("--no-ablation", action="store_true")
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    policies = [p.strip() for p in args.policies.split(",")]
    seeds = list(range(1, args.seeds + 1))
    solver = args.solver if args.solver != "chain" else None

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out) if args.out else REPO_ROOT / "evidence" / "eval_reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"MedBalance-Q Replay Evaluation")
    print(f"  Seeds: {len(seeds)}, Days: {args.days}, Policies: {policies}")
    print(f"  Solver: {solver or 'full chain'}")
    print()

    all_runs: dict[str, list[RunResult]] = {}
    total_t0 = time.perf_counter()

    for pol in policies:
        print(f"-- Policy {pol} --")
        runs: list[RunResult] = []
        for seed in seeds:
            t0 = time.perf_counter()
            result = run_single(seed, pol, args.days, solver_override=solver)
            elapsed = time.perf_counter() - t0
            print(f"  seed={seed:2d}: stockout={result.stockout_days:3d} expired={result.expired_units:5d} "
                  f"violations={result.violations} ({elapsed:.1f}s)")
            runs.append(result)
        all_runs[pol] = runs
        print()

    # Ablation variants
    ablation_runs: dict[str, list[RunResult]] = {}
    if not args.no_ablation and "D" in policies:
        ablation_policies = ["D-noF4", "D-noForecast", "D-noGamma"]
        for abl_pol in ablation_policies:
            print(f"-- Ablation: {abl_pol} --")
            runs = []
            for seed in seeds:
                t0 = time.perf_counter()
                result = run_single(seed, abl_pol, args.days, solver_override=solver)
                elapsed = time.perf_counter() - t0
                print(f"  seed={seed:2d}: stockout={result.stockout_days:3d} violations={result.violations} ({elapsed:.1f}s)")
                runs.append(result)
            ablation_runs[abl_pol] = runs
            print()

    total_elapsed = time.perf_counter() - total_t0
    print(f"Total time: {total_elapsed:.1f}s")

    # Aggregate
    agg_results = [aggregate(runs) for pol, runs in all_runs.items()]
    abl_agg = [aggregate(runs) for pol, runs in ablation_runs.items()]

    # Write JSON report
    report = {
        "timestamp": ts,
        "n_seeds": len(seeds),
        "n_days": args.days,
        "solver_override": solver,
        "total_time_s": round(total_elapsed, 1),
        "aggregated": [a.to_dict() for a in agg_results],
        "ablation": [a.to_dict() for a in abl_agg],
        "per_seed": {
            pol: [r.to_dict() for r in runs]
            for pol, runs in {**all_runs, **ablation_runs}.items()
        },
    }

    report_path = out_dir / f"replay_{ts}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nJSON report: {report_path}")

    # Charts
    chart_files = generate_charts(agg_results, out_dir)
    for cf in chart_files:
        print(f"Chart: {cf}")

    # Markdown summary
    md = markdown_summary(agg_results, abl_agg)
    md_path = out_dir / f"replay_{ts}.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"Summary: {md_path}")

    # Print summary table (replace non-ASCII for Windows console)
    print()
    print(md.encode("ascii", errors="replace").decode("ascii"))

    return report


if __name__ == "__main__":
    main()
