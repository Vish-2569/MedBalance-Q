"""Test fixtures for core-api tests using SQLite in-memory DB."""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

# Ensure medbal_common is importable
libs_path = str(Path(__file__).resolve().parents[3] / "libs" / "medbal_common")
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

# Set env vars before importing settings
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("USE_FIXTURES", "0")
os.environ.setdefault("SIM_START_DATE", "2026-11-01")
os.environ.setdefault("SIM_DAY_SECONDS", "9999999")

from medbal_common import audit
from medbal_common.db import get_engine, get_session_factory, session_scope

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS facility (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, level TEXT NOT NULL,
    lat REAL NOT NULL, lon REAL NOT NULL, cold_storage_ok INTEGER NOT NULL DEFAULT 1,
    cold_storage_note TEXT, report_format TEXT NOT NULL DEFAULT 'fhir',
    report_lang TEXT NOT NULL DEFAULT 'en', taluk TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS drug (
    code TEXT PRIMARY KEY, name TEXT NOT NULL, ven TEXT NOT NULL, unit TEXT NOT NULL,
    pack_size INTEGER NOT NULL, cold_chain INTEGER NOT NULL DEFAULT 0,
    temp_min_c REAL, temp_max_c REAL, controlled INTEGER NOT NULL DEFAULT 0,
    min_residual_days INTEGER NOT NULL DEFAULT 30, unit_cost_inr REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS drug_alias (
    id INTEGER PRIMARY KEY AUTOINCREMENT, drug_code TEXT NOT NULL REFERENCES drug(code),
    alias TEXT NOT NULL, lang TEXT NOT NULL DEFAULT 'en', source TEXT,
    UNIQUE (drug_code, alias)
);
CREATE TABLE IF NOT EXISTS route (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    src_facility_id TEXT NOT NULL, dst_facility_id TEXT NOT NULL,
    distance_km REAL NOT NULL, transit_hours REAL NOT NULL,
    cold_capable INTEGER NOT NULL DEFAULT 0,
    cost_ambient_inr REAL NOT NULL DEFAULT 0, cost_cold_inr REAL NOT NULL DEFAULT 0,
    UNIQUE (src_facility_id, dst_facility_id)
);
CREATE TABLE IF NOT EXISTS vehicle (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL,
    cold_chain INTEGER NOT NULL DEFAULT 0, capacity_units INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS policy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id TEXT NOT NULL, drug_code TEXT NOT NULL,
    min_reserve_days INTEGER NOT NULL DEFAULT 7, target_days INTEGER NOT NULL DEFAULT 21,
    max_stock_days INTEGER NOT NULL DEFAULT 60, lead_time_days INTEGER NOT NULL DEFAULT 3,
    UNIQUE (facility_id, drug_code)
);
CREATE TABLE IF NOT EXISTS lot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id TEXT NOT NULL, drug_code TEXT NOT NULL, batch_no TEXT NOT NULL,
    expiry TEXT NOT NULL, qty INTEGER NOT NULL DEFAULT 0,
    received_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (facility_id, drug_code, batch_no)
);
CREATE TABLE IF NOT EXISTS consumption_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id TEXT NOT NULL, drug_code TEXT NOT NULL,
    date TEXT NOT NULL, qty INTEGER NOT NULL DEFAULT 0,
    UNIQUE (facility_id, drug_code, date)
);
CREATE TABLE IF NOT EXISTS forecast (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id TEXT NOT NULL, drug_code TEXT NOT NULL,
    horizon_days INTEGER NOT NULL, daily_rate REAL NOT NULL,
    method TEXT NOT NULL, confidence REAL NOT NULL,
    context_multiplier REAL NOT NULL DEFAULT 1.0,
    adjusted_rate REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (facility_id, drug_code)
);
CREATE TABLE IF NOT EXISTS plan_run (
    id TEXT PRIMARY KEY, mode TEXT NOT NULL DEFAULT 'live',
    solver_tier TEXT NOT NULL, energy REAL, gap_to_milp REAL,
    variables INTEGER, constraints INTEGER, transfers INTEGER NOT NULL DEFAULT 0,
    shortage_reduction REAL, expiry_avoided INTEGER, cost_inr REAL,
    params TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS candidate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_run_id TEXT NOT NULL, chunk_id TEXT,
    facility_id TEXT NOT NULL, drug_code TEXT NOT NULL, batch_no TEXT NOT NULL,
    destination_id TEXT NOT NULL, usable INTEGER NOT NULL, score REAL NOT NULL,
    feasibility TEXT, selected INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS transfer_order (
    id TEXT PRIMARY KEY, dta_number TEXT NOT NULL UNIQUE,
    plan_run_id TEXT NOT NULL, src_facility_id TEXT NOT NULL,
    dst_facility_id TEXT NOT NULL, drug_code TEXT NOT NULL,
    drug_name TEXT NOT NULL, batch_no TEXT NOT NULL,
    qty INTEGER NOT NULL, usable INTEGER NOT NULL, score REAL,
    status TEXT NOT NULL DEFAULT 'proposed',
    temperature_req TEXT NOT NULL DEFAULT 'ambient',
    vehicle_id TEXT, approved_by TEXT, approved_at TEXT,
    rejected_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS regret_entry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_run_id TEXT NOT NULL, order_id TEXT,
    alternative TEXT NOT NULL, reason TEXT NOT NULL, delta_score REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS custody_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL, event_type TEXT NOT NULL, actor TEXT NOT NULL,
    timestamp TEXT NOT NULL, location TEXT, temperature_c REAL, notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS stock_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id TEXT NOT NULL, reported_at TEXT NOT NULL,
    format TEXT NOT NULL, raw_text TEXT, raw_file_path TEXT,
    llm_model TEXT, prompt_ref TEXT, confidence REAL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS extraction_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL, drug_code TEXT, drug_name_raw TEXT NOT NULL,
    batch_no TEXT, expiry TEXT, qty INTEGER, unit TEXT,
    confidence REAL NOT NULL DEFAULT 0, flags TEXT NOT NULL DEFAULT '[]',
    review_status TEXT NOT NULL DEFAULT 'auto',
    resolved_by TEXT, resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        for stmt in SQLITE_SCHEMA.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.execute(text(audit.CREATE_AUDIT_TABLE))
        conn.commit()
    return engine


@pytest.fixture(autouse=True)
def _patch_db(db_engine, monkeypatch):
    """Patch medbal_common.db to use our test engine."""
    import medbal_common.db as db_mod
    monkeypatch.setattr(db_mod, "_engine", db_engine)
    monkeypatch.setattr(db_mod, "_session_factory", get_session_factory(db_engine))


@pytest.fixture
def seed_data(db_engine):
    """Insert minimal seed data for testing."""
    with db_engine.connect() as conn:
        conn.execute(text("DELETE FROM custody_event"))
        conn.execute(text("DELETE FROM regret_entry"))
        conn.execute(text("DELETE FROM candidate"))
        conn.execute(text("DELETE FROM transfer_order"))
        conn.execute(text("DELETE FROM plan_run"))
        conn.execute(text("DELETE FROM lot"))
        conn.execute(text("DELETE FROM consumption_daily"))
        conn.execute(text("DELETE FROM forecast"))
        conn.execute(text("DELETE FROM policy"))
        conn.execute(text("DELETE FROM route"))
        conn.execute(text("DELETE FROM vehicle"))
        conn.execute(text("DELETE FROM drug"))
        conn.execute(text("DELETE FROM facility"))
        conn.execute(text("DELETE FROM audit_log"))

        conn.execute(text(
            "INSERT INTO facility VALUES ('W0','SIM-Warehouse','WH',12.97,77.59,1,NULL,'fhir','en','South',datetime('now'))"
        ))
        conn.execute(text(
            "INSERT INTO facility VALUES ('H1','SIM-DH Jayanagar','DH',12.925,77.593,1,NULL,'fhir','en','South',datetime('now'))"
        ))
        conn.execute(text(
            "INSERT INTO facility VALUES ('H4','SIM-PHC Hesaraghatta','PHC',13.14,77.48,0,'ILR under repair','text','en','Yelahanka',datetime('now'))"
        ))
        conn.execute(text(
            "INSERT INTO drug VALUES ('INSULIN','Insulin Human 40 IU/ml','V','vial',1,1,2.0,8.0,0,60,45.00,datetime('now'))"
        ))
        conn.execute(text(
            "INSERT INTO drug VALUES ('PCM','Paracetamol 500mg','E','tablet',10,0,NULL,NULL,0,30,0.50,datetime('now'))"
        ))
        conn.execute(text(
            "INSERT INTO route (src_facility_id,dst_facility_id,distance_km,transit_hours,cold_capable,cost_ambient_inr,cost_cold_inr) "
            "VALUES ('H4','H1',30.5,0.76,0,244.0,457.5)"
        ))
        conn.execute(text(
            "INSERT INTO vehicle VALUES ('CV-01','SIM-Cold Van','cold_van',1,5000,datetime('now'))"
        ))
        conn.execute(text(
            "INSERT INTO policy (facility_id,drug_code,min_reserve_days,target_days,max_stock_days,lead_time_days) "
            "VALUES ('H1','INSULIN',7,21,60,3)"
        ))
        conn.execute(text(
            "INSERT INTO lot (facility_id,drug_code,batch_no,expiry,qty) VALUES ('H4','INSULIN','B-INS-H4-001','2026-11-19',50)"
        ))
        conn.execute(text(
            "INSERT INTO lot (facility_id,drug_code,batch_no,expiry,qty) VALUES ('H1','INSULIN','B-INS-H1-001','2026-11-15',5)"
        ))
        conn.execute(text(
            "INSERT INTO lot (facility_id,drug_code,batch_no,expiry,qty) VALUES ('H1','PCM','B-PCM-H1-001','2027-04-15',800)"
        ))
        conn.commit()
    return True
