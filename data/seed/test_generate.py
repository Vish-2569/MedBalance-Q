"""Tests for the MedBalance-Q seed generator."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from generate import STORY_LOTS, generate

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
SQL_OUTPUT = REPO_ROOT / "db" / "init" / "002_seed.sql"
HOSPITALS_DIR = SCRIPT_DIR / "hospitals"

SEED = 42


@pytest.fixture(scope="module", autouse=True)
def run_generator():
    generate(SEED)


# ── determinism ──────────────────────────────────────────────────────

def test_determinism():
    sql1 = SQL_OUTPUT.read_text(encoding="utf-8")
    generate(SEED)
    sql2 = SQL_OUTPUT.read_text(encoding="utf-8")
    assert sql1 == sql2, "Same seed must produce identical SQL"


def test_different_seed_differs():
    sql1 = SQL_OUTPUT.read_text(encoding="utf-8")
    generate(99)
    sql2 = SQL_OUTPUT.read_text(encoding="utf-8")
    assert sql1 != sql2
    generate(SEED)


# ── SQL file structure ───────────────────────────────────────────────

def test_sql_has_facility_inserts():
    sql = SQL_OUTPUT.read_text(encoding="utf-8")
    assert "INSERT INTO facility" in sql


def test_sql_has_drug_inserts():
    sql = SQL_OUTPUT.read_text(encoding="utf-8")
    assert "INSERT INTO drug " in sql


def test_sql_has_drug_alias_inserts():
    sql = SQL_OUTPUT.read_text(encoding="utf-8")
    assert "INSERT INTO drug_alias" in sql


def test_sql_has_lot_inserts():
    sql = SQL_OUTPUT.read_text(encoding="utf-8")
    assert "INSERT INTO lot" in sql


def test_sql_has_route_inserts():
    sql = SQL_OUTPUT.read_text(encoding="utf-8")
    assert "INSERT INTO route" in sql


def test_sql_has_policy_inserts():
    sql = SQL_OUTPUT.read_text(encoding="utf-8")
    assert "INSERT INTO policy" in sql


def test_sql_has_vehicle_inserts():
    sql = SQL_OUTPUT.read_text(encoding="utf-8")
    assert "INSERT INTO vehicle" in sql


def test_sql_has_consumption_inserts():
    sql = SQL_OUTPUT.read_text(encoding="utf-8")
    assert "INSERT INTO consumption_daily" in sql


# ── routes: 5 facilities → 20 directed pairs ────────────────────────

def test_route_count():
    sql = SQL_OUTPUT.read_text(encoding="utf-8")
    route_lines = [l for l in sql.splitlines() if l.startswith("INSERT INTO route")]
    assert len(route_lines) == 20


# ── hospital JSON files ─────────────────────────────────────────────

@pytest.mark.parametrize("hosp", ["h1", "h2", "h3", "h4"])
def test_hospital_json_exists(hosp):
    path = HOSPITALS_DIR / f"{hosp}.json"
    assert path.exists(), f"Missing {path}"


@pytest.mark.parametrize("hosp", ["h1", "h2", "h3", "h4"])
def test_hospital_json_structure(hosp):
    path = HOSPITALS_DIR / f"{hosp}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "facility_id" in data
    assert "lots" in data
    assert "consumption_last_30d" in data
    assert isinstance(data["lots"], list)
    assert isinstance(data["consumption_last_30d"], dict)


# ── all lot quantities >= 0 ──────────────────────────────────────────

def test_all_lot_quantities_positive():
    for fac_id, drug_code, batch_no, expiry, qty in STORY_LOTS:
        assert qty >= 0, f"Lot {batch_no} has qty {qty}"


def test_consumption_quantities_non_negative():
    sql = SQL_OUTPUT.read_text(encoding="utf-8")
    for line in sql.splitlines():
        if "INSERT INTO consumption_daily" in line:
            qty_match = re.search(r",\s*(\d+)\);$", line)
            assert qty_match, f"Could not parse qty from: {line}"
            assert int(qty_match.group(1)) >= 0


# ── story invariants ─────────────────────────────────────────────────

def test_h4_insulin_lot():
    h4_insulin = [
        (fac, dc, bn, exp, qty)
        for fac, dc, bn, exp, qty in STORY_LOTS
        if fac == "H4" and dc == "INSULIN"
    ]
    assert len(h4_insulin) == 1
    _, _, batch, expiry, qty = h4_insulin[0]
    assert qty == 50
    assert batch == "B-INS-H4-001"
    assert expiry.startswith("2026-11")


def test_h1_insulin_shortage():
    h1_insulin = [qty for fac, dc, _, _, qty in STORY_LOTS if fac == "H1" and dc == "INSULIN"]
    assert sum(h1_insulin) <= 10


def test_h3_ors_low():
    h3_ors = [qty for fac, dc, _, _, qty in STORY_LOTS if fac == "H3" and dc == "ORS"]
    assert sum(h3_ors) <= 30


def test_h2_pcm_overstock():
    h2_pcm = [qty for fac, dc, _, _, qty in STORY_LOTS if fac == "H2" and dc == "PCM"]
    assert sum(h2_pcm) >= 1000


def test_h2_ifa_overstock():
    h2_ifa = [qty for fac, dc, _, _, qty in STORY_LOTS if fac == "H2" and dc == "IFA"]
    assert sum(h2_ifa) >= 2000


def test_h2_morphine_exists():
    h2_morphine = [qty for fac, dc, _, _, qty in STORY_LOTS if fac == "H2" and dc == "MORPHINE"]
    assert len(h2_morphine) >= 1
    assert all(q > 0 for q in h2_morphine)


# ── drug aliases include Kannada ─────────────────────────────────────

def test_kannada_aliases_in_sql():
    sql = SQL_OUTPUT.read_text(encoding="utf-8")
    assert "'kn'" in sql, "Should have Kannada aliases"
    kannada_lines = [l for l in sql.splitlines() if "drug_alias" in l and "'kn'" in l]
    assert len(kannada_lines) >= 10, f"Expected ≥10 Kannada aliases, got {len(kannada_lines)}"
