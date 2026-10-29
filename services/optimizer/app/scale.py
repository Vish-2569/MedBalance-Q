"""Synthetic 40-facility district generator for scale-mode evaluation.

Generates 5 taluks × 8 facilities with the same drug set as the live fixture.
In-memory only — no containers, no DB writes.
"""
from __future__ import annotations

import math
import random
from datetime import date, timedelta
from typing import Any

from .snapshot import Snapshot, Facility, Drug, Route, Vehicle, Lot, Position, Policy


TALUK_NAMES = ["Anekal", "Yelahanka", "Devanahalli", "Hosakote", "Nelamangala"]

DRUGS = [
    ("PCM", "Paracetamol 500mg", "E", "tablet", 10, False, False, 30, 2.5),
    ("AMOX", "Amoxicillin 500mg", "E", "capsule", 10, False, False, 30, 5.0),
    ("IFA", "Iron Folic Acid", "E", "tablet", 100, False, False, 30, 0.5),
    ("ORS", "ORS Sachet", "E", "sachet", 25, False, False, 30, 3.0),
    ("INSULIN", "Insulin Human 40IU/ml", "V", "vial", 1, True, False, 60, 75.0),
    ("OXYTOCIN", "Oxytocin 5IU/ml", "V", "vial", 1, True, False, 60, 40.0),
    ("RL", "Ringer Lactate 500ml", "V", "bottle", 1, False, False, 30, 25.0),
    ("AMLODIPINE", "Amlodipine 5mg", "E", "tablet", 10, False, False, 30, 1.5),
    ("METFORMIN", "Metformin 500mg", "E", "tablet", 10, False, False, 30, 2.0),
    ("MORPHINE", "Morphine 10mg", "V", "amp", 5, False, True, 60, 35.0),
]


def generate_scale_snapshot(
    n_facilities: int = 40,
    n_taluks: int = 5,
    seed: int = 42,
    today: date | None = None,
) -> tuple[Snapshot, dict[str, str]]:
    """Generate a synthetic district snapshot. Returns (snapshot, taluk_map)."""
    rng = random.Random(seed)
    today = today or date(2026, 11, 1)
    facs_per_taluk = n_facilities // n_taluks

    snap = Snapshot(today=today)
    taluk_map: dict[str, str] = {}

    # Drugs
    for code, name, ven, unit, pack, cold, ctrl, min_res, cost in DRUGS:
        snap.drugs[code] = Drug(code, name, ven, unit, pack, cold, ctrl, min_res, cost)

    # Warehouse
    snap.facilities["W0"] = Facility("W0", "SIM-District Warehouse", "DW", True)

    # Facilities: 5 taluks × 8
    levels = ["DH", "TH", "CHC", "PHC"]
    for t_idx in range(n_taluks):
        taluk = TALUK_NAMES[t_idx] if t_idx < len(TALUK_NAMES) else f"Taluk-{t_idx}"
        for f_idx in range(facs_per_taluk):
            fid = f"H{t_idx * facs_per_taluk + f_idx + 1:02d}"
            level = levels[f_idx % len(levels)]
            cold_storage = level in ("DH", "TH") or rng.random() < 0.3
            snap.facilities[fid] = Facility(
                fid, f"SIM-{taluk}-{level}-{f_idx+1}", level, cold_storage,
            )
            taluk_map[fid] = taluk

    fac_ids = [f for f in snap.facilities if f != "W0"]

    # Routes: within same taluk (short) + between adjacent taluks (longer)
    for i, src in enumerate(fac_ids):
        for j, dst in enumerate(fac_ids):
            if src == dst:
                continue
            t_src = taluk_map[src]
            t_dst = taluk_map[dst]
            same_taluk = t_src == t_dst

            base_dist = rng.uniform(5, 25) if same_taluk else rng.uniform(30, 80)
            transit_h = base_dist / 30  # ~30 km/h
            cold_ok = rng.random() < (0.8 if same_taluk else 0.4)
            cost_amb = base_dist * 3.0
            cost_cold = base_dist * 5.0

            snap.routes[(src, dst)] = Route(
                src, dst, round(base_dist, 1), round(transit_h, 2),
                cold_ok, round(cost_amb, 2), round(cost_cold, 2),
            )

    # W0 routes
    for fid in fac_ids:
        dist = rng.uniform(15, 60)
        snap.routes[("W0", fid)] = Route("W0", fid, round(dist, 1), round(dist/30, 2), True, round(dist*3, 2), round(dist*5, 2))
        snap.routes[(fid, "W0")] = Route(fid, "W0", round(dist, 1), round(dist/30, 2), True, round(dist*3, 2), round(dist*5, 2))

    # Vehicles
    snap.vehicles = [
        Vehicle("V1", "Cold Van", True, 5000),
        Vehicle("V2", "Ambulance", True, 2000),
        Vehicle("V3", "Van-1", False, 10000),
        Vehicle("V4", "Van-2", False, 10000),
    ]

    # Lots + Positions
    non_ctrl_drugs = [d for d in snap.drugs.values() if not d.controlled]

    for fid in fac_ids:
        level = snap.facilities[fid].level
        rate_scale = {"DH": 3.0, "TH": 2.0, "CHC": 1.0, "PHC": 0.5}.get(level, 1.0)

        for drug in non_ctrl_drugs:
            rate = rng.uniform(2, 20) * rate_scale
            target_days = 21

            # Some facilities overstocked (expiry risk), some understocked (shortage)
            r = rng.random()
            if r < 0.25:
                # Overstocked, near expiry
                qty = int(rate * rng.uniform(30, 60))
                expiry = today + timedelta(days=rng.randint(15, 40))
                shortage = 0
            elif r < 0.5:
                # Understocked
                qty = int(rate * rng.uniform(1, 7))
                expiry = today + timedelta(days=rng.randint(45, 120))
                shortage = max(0, int(rate * target_days) - qty)
            else:
                # Normal
                qty = int(rate * rng.uniform(10, 25))
                expiry = today + timedelta(days=rng.randint(30, 90))
                shortage = max(0, int(rate * target_days) - qty)

            if qty > 0:
                batch = f"B-{fid}-{drug.code}-{rng.randint(1, 999):03d}"
                lot = Lot(fid, drug.code, batch, expiry, qty)
                snap.lots.append(lot)
                snap.lots_by_fd.setdefault((fid, drug.code), []).append(lot)

            effective = min(qty, int(rate * min((expiry - today).days, target_days)))
            at_risk = max(0, qty - effective)
            reserve = int(rate * 7)

            snap.positions[(fid, drug.code)] = Position(
                fid, drug.code, effective, at_risk, reserve, shortage, rate, target_days,
            )

            snap.policies[(fid, drug.code)] = Policy(fid, drug.code, 7, target_days, 3)

    return snap, taluk_map
