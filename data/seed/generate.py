"""MedBalance-Q seed generator.

Produces deterministic SQL seed data and per-hospital JSON state files
from district.yaml and drugs.yaml.

Usage: python -I generate.py --seed 42
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
from datetime import date, timedelta
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
SQL_OUTPUT = REPO_ROOT / "db" / "init" / "002_seed.sql"
HOSPITALS_DIR = SCRIPT_DIR / "hospitals"

SIM_START_DATE = date(2026, 11, 1)

# ── demand rates: drug_code -> {level: daily_base_rate} ──────────────
DEMAND = {
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

POLICY_BY_LEVEL = {
    "DH":  {"min_reserve_days": 7, "target_days": 21, "max_stock_days": 60, "lead_time_days": 3},
    "TH":  {"min_reserve_days": 7, "target_days": 21, "max_stock_days": 60, "lead_time_days": 3},
    "CHC": {"min_reserve_days": 5, "target_days": 14, "max_stock_days": 45, "lead_time_days": 4},
    "PHC": {"min_reserve_days": 3, "target_days": 10, "max_stock_days": 30, "lead_time_days": 5},
}

# ── engineered lots ──────────────────────────────────────────────────
STORY_LOTS = [
    # H1 — DH Jayanagar: shortage of cold-chain drugs
    ("H1", "INSULIN",     "B-INS-H1-001", "2026-11-15",   5),
    ("H1", "OXYTOCIN",    "B-OXY-H1-001", "2026-11-20",   3),
    ("H1", "PCM",         "B-PCM-H1-001", "2027-04-15", 800),
    ("H1", "AMOX",        "B-AMX-H1-001", "2027-03-20", 400),
    ("H1", "CEFTRIAXONE", "B-CFT-H1-001", "2027-02-28", 100),
    ("H1", "METFORMIN",   "B-MET-H1-001", "2027-05-01", 300),
    ("H1", "AMLODIPINE",  "B-AML-H1-001", "2027-04-15", 200),
    ("H1", "IFA",         "B-IFA-H1-001", "2027-03-01", 500),
    ("H1", "RL",          "B-RL-H1-001",  "2027-06-01", 100),
    # H2 — TGH Anekal: overstocked, near-expiry
    ("H2", "IFA",         "B-IFA-H2-001", "2026-12-10", 3000),
    ("H2", "PCM",         "B-PCM-H2-001", "2026-11-25", 1500),
    ("H2", "AMOX",        "B-AMX-H2-001", "2026-12-05",  800),
    ("H2", "METFORMIN",   "B-MET-H2-001", "2027-06-30",  200),
    ("H2", "MORPHINE",    "B-MOR-H2-001", "2027-08-15",   15),
    ("H2", "OXYTOCIN",    "B-OXY-H2-001", "2027-04-01",   40),
    ("H2", "CEFTRIAXONE", "B-CFT-H2-001", "2027-05-01",   60),
    ("H2", "INSULIN",     "B-INS-H2-001", "2027-03-01",   30),
    # H3 — CHC Yelahanka: low ORS before dengue
    ("H3", "ORS",         "B-ORS-H3-001", "2027-01-15",   20),
    ("H3", "PCM",         "B-PCM-H3-001", "2027-05-01",  200),
    ("H3", "TD",          "B-TD-H3-001",  "2027-09-01",   50),
    ("H3", "AMOX",        "B-AMX-H3-001", "2027-03-15",   80),
    ("H3", "RL",          "B-RL-H3-001",  "2027-04-01",   30),
    ("H3", "METFORMIN",   "B-MET-H3-001", "2027-06-01",   50),
    # H4 — PHC Hesaraghatta: insulin lot that should transfer
    ("H4", "INSULIN",     "B-INS-H4-001", "2026-11-19",   50),
    ("H4", "PCM",         "B-PCM-H4-001", "2027-03-01",   60),
    ("H4", "ORS",         "B-ORS-H4-001", "2027-02-15",   30),
    ("H4", "AMLODIPINE",  "B-AML-H4-001", "2027-07-01",   40),
    ("H4", "AMOX",        "B-AMX-H4-001", "2027-02-01",   20),
    # W0 — Warehouse: buffer stock of everything
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


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


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


def sql_str(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def load_yaml(name: str) -> dict:
    path = SCRIPT_DIR / name
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate(seed: int) -> None:
    rng = random.Random(seed)
    district = load_yaml("district.yaml")
    drugs_data = load_yaml("drugs.yaml")

    facilities = district["facilities"]
    vehicles = district["vehicles"]
    drugs = drugs_data["drugs"]

    fac_by_id = {f["id"]: f for f in facilities}
    drug_by_code = {d["code"]: d for d in drugs}

    lines: list[str] = []
    lines.append(f"-- MedBalance-Q seed data (seed={seed})")
    lines.append(f"-- sim_start_date = {SIM_START_DATE.isoformat()}")
    lines.append(f"-- Generated deterministically — do not edit by hand.")
    lines.append("")

    # ── facilities ───────────────────────────────────────────────────
    for f in facilities:
        lines.append(
            f"INSERT INTO facility (id, name, level, lat, lon, "
            f"cold_storage_ok, cold_storage_note, report_format, report_lang, taluk) "
            f"VALUES ({sql_str(f['id'])}, {sql_str(f['name'])}, {sql_str(f['level'])}, "
            f"{f['lat']}, {f['lon']}, "
            f"{sql_str(f['cold_storage_ok'])}, {sql_str(f.get('cold_storage_note'))}, "
            f"{sql_str(f.get('report_format', 'fhir'))}, {sql_str(f.get('report_lang', 'en'))}, "
            f"{sql_str(f.get('taluk'))});"
        )
    lines.append("")

    # ── drugs ────────────────────────────────────────────────────────
    for d in drugs:
        lines.append(
            f"INSERT INTO drug (code, name, ven, unit, pack_size, cold_chain, "
            f"temp_min_c, temp_max_c, controlled, min_residual_days, unit_cost_inr) "
            f"VALUES ({sql_str(d['code'])}, {sql_str(d['name'])}, {sql_str(d['ven'])}, "
            f"{sql_str(d['unit'])}, {d['pack_size']}, {sql_str(d['cold_chain'])}, "
            f"{sql_str(d.get('temp_min_c'))}, {sql_str(d.get('temp_max_c'))}, "
            f"{sql_str(d['controlled'])}, {d['min_residual_days']}, {d['unit_cost_inr']});"
        )
    lines.append("")

    # ── drug aliases ─────────────────────────────────────────────────
    for d in drugs:
        for a in d.get("aliases", []):
            lines.append(
                f"INSERT INTO drug_alias (drug_code, alias, lang, source) "
                f"VALUES ({sql_str(d['code'])}, {sql_str(a['alias'])}, "
                f"{sql_str(a['lang'])}, {sql_str(a.get('source'))});"
            )
    lines.append("")

    # ── vehicles ─────────────────────────────────────────────────────
    for v in vehicles:
        lines.append(
            f"INSERT INTO vehicle (id, name, type, cold_chain, capacity_units) "
            f"VALUES ({sql_str(v['id'])}, {sql_str(v['name'])}, {sql_str(v['type'])}, "
            f"{sql_str(v['cold_chain'])}, {v['capacity_units']});"
        )
    lines.append("")

    # ── routes (all directed pairs) ──────────────────────────────────
    route_count = 0
    for a in facilities:
        for b in facilities:
            if a["id"] == b["id"]:
                continue
            dist = haversine(a["lat"], a["lon"], b["lat"], b["lon"]) * 1.3
            transit_h = max(0.5, dist / 40.0)
            cold_ok = a["cold_storage_ok"] and b["cold_storage_ok"]
            cost_amb = round(8.0 * dist, 2)
            cost_cold = round(15.0 * dist, 2)
            lines.append(
                f"INSERT INTO route (src_facility_id, dst_facility_id, distance_km, "
                f"transit_hours, cold_capable, cost_ambient_inr, cost_cold_inr) "
                f"VALUES ({sql_str(a['id'])}, {sql_str(b['id'])}, {round(dist, 2)}, "
                f"{round(transit_h, 2)}, {sql_str(cold_ok)}, {cost_amb}, {cost_cold});"
            )
            route_count += 1
    lines.append("")

    # ── policies ─────────────────────────────────────────────────────
    for f in facilities:
        if f["level"] == "WH":
            continue
        policy = POLICY_BY_LEVEL[f["level"]]
        for d in drugs:
            lines.append(
                f"INSERT INTO policy (facility_id, drug_code, min_reserve_days, "
                f"target_days, max_stock_days, lead_time_days) "
                f"VALUES ({sql_str(f['id'])}, {sql_str(d['code'])}, "
                f"{policy['min_reserve_days']}, {policy['target_days']}, "
                f"{policy['max_stock_days']}, {policy['lead_time_days']});"
            )
    lines.append("")

    # ── lots ─────────────────────────────────────────────────────────
    for fac_id, drug_code, batch_no, expiry, qty in STORY_LOTS:
        lines.append(
            f"INSERT INTO lot (facility_id, drug_code, batch_no, expiry, qty) "
            f"VALUES ({sql_str(fac_id)}, {sql_str(drug_code)}, {sql_str(batch_no)}, "
            f"{sql_str(expiry)}, {qty});"
        )
    lines.append("")

    # ── consumption history (90 days) ────────────────────────────────
    history_start = SIM_START_DATE - timedelta(days=90)
    consumption_count = 0
    # Build consumption data keyed by (facility_id, drug_code) for hospital JSON later
    consumption_data: dict[tuple[str, str], list[dict]] = {}

    for f in facilities:
        if f["level"] == "WH":
            continue
        level = f["level"]
        for d in drugs:
            base_rate = DEMAND.get(d["code"], {}).get(level, 0)
            if base_rate <= 0:
                continue
            daily_records = []
            for day_offset in range(90):
                day = history_start + timedelta(days=day_offset)
                weekday = day.weekday()
                if weekday < 5:
                    factor = 1.0
                elif weekday == 5:
                    factor = 0.6
                else:
                    factor = 0.3
                qty = poisson(rng, base_rate * factor)
                lines.append(
                    f"INSERT INTO consumption_daily (facility_id, drug_code, "
                    f"date, qty) VALUES ({sql_str(f['id'])}, "
                    f"{sql_str(d['code'])}, {sql_str(day.isoformat())}, {qty});"
                )
                daily_records.append({"date": day.isoformat(), "qty": qty})
                consumption_count += 1
            consumption_data[(f["id"], d["code"])] = daily_records
    lines.append("")

    # ── write SQL ────────────────────────────────────────────────────
    os.makedirs(SQL_OUTPUT.parent, exist_ok=True)
    SQL_OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ── write hospital JSONs ─────────────────────────────────────────
    os.makedirs(HOSPITALS_DIR, exist_ok=True)
    for f in facilities:
        if f["level"] == "WH":
            continue
        fac_id = f["id"]
        hosp_lots = [
            {
                "facility_id": fac_id,
                "drug_code": dc,
                "batch_no": bn,
                "expiry": exp,
                "qty": qty,
            }
            for (fid, dc, bn, exp, qty) in STORY_LOTS
            if fid == fac_id
        ]
        # Last 30 days of consumption
        last30 = {}
        for d in drugs:
            key = (fac_id, d["code"])
            if key in consumption_data:
                records = consumption_data[key]
                last30[d["code"]] = records[-30:]

        hospital_state = {
            "facility_id": fac_id,
            "facility_name": f["name"],
            "level": f["level"],
            "cold_storage_ok": f["cold_storage_ok"],
            "lots": hosp_lots,
            "consumption_last_30d": last30,
        }
        out_path = HOSPITALS_DIR / f"{fac_id.lower()}.json"
        out_path.write_text(
            json.dumps(hospital_state, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # ── summary ──────────────────────────────────────────────────────
    print(f"Seed {seed}: generated {SQL_OUTPUT.name}")
    print(f"  Facilities:   {len(facilities)}")
    print(f"  Drugs:        {len(drugs)}")
    print(f"  Aliases:      {sum(len(d.get('aliases', [])) for d in drugs)}")
    print(f"  Vehicles:     {len(vehicles)}")
    print(f"  Routes:       {route_count}")
    print(f"  Policies:     {sum(1 for f in facilities if f['level'] != 'WH') * len(drugs)}")
    print(f"  Lots:         {len(STORY_LOTS)}")
    print(f"  Consumption:  {consumption_count} daily records (90 days)")
    print(f"  Hospital JSONs: {[f'{f['id'].lower()}.json' for f in facilities if f['level'] != 'WH']}")


def main():
    parser = argparse.ArgumentParser(description="Generate MedBalance-Q seed data")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    args = parser.parse_args()
    generate(args.seed)


if __name__ == "__main__":
    main()
