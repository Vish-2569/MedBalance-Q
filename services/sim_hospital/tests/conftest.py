"""Test fixtures for sim-hospital tests."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

libs_path = str(Path(__file__).resolve().parents[3] / "libs" / "medbal_common")
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

svc_path = str(Path(__file__).resolve().parents[1])
if svc_path not in sys.path:
    sys.path.insert(0, svc_path)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("USE_FIXTURES", "0")
os.environ.setdefault("SIM_START_DATE", "2026-11-01")
os.environ.setdefault("SIM_DAY_SECONDS", "9999999")
os.environ.setdefault("HOSPITAL_ID", "h1")

from app import stock_db


@pytest.fixture(autouse=True)
def fresh_db():
    """Reset the in-memory DB for each test."""
    stock_db.init_db()
    stock_db.load_seed("h1")
    yield
    if stock_db._conn:
        stock_db._conn.close()
        stock_db._conn = None
