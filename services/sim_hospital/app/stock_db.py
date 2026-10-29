"""SQLite in-memory stock database for a simulated hospital."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()
_base_rates: dict[str, float] = {}
_hospital_id: str = ""
_facility_id: str = ""

SCHEMA = """
CREATE TABLE IF NOT EXISTS lots (
    drug_code TEXT NOT NULL,
    batch_no TEXT NOT NULL,
    expiry TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    PRIMARY KEY (drug_code, batch_no)
);
CREATE TABLE IF NOT EXISTS consumption_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    drug_code TEXT NOT NULL,
    demanded INTEGER NOT NULL DEFAULT 0,
    dispensed INTEGER NOT NULL DEFAULT 0,
    stockout_qty INTEGER NOT NULL DEFAULT 0
);
"""


def _find_seed_path(hospital_id: str) -> Path:
    p = Path(f"/app/data/seed/hospitals/{hospital_id}.json")
    if p.exists():
        return p
    for base in [
        Path(__file__).resolve().parents[3],
        Path(__file__).resolve().parents[4],
        Path.cwd(),
    ]:
        p = base / "data" / "seed" / "hospitals" / f"{hospital_id}.json"
        if p.exists():
            return p
    raise FileNotFoundError(f"Cannot find seed file for {hospital_id}")


def init_db() -> sqlite3.Connection:
    global _conn
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _conn = conn
    return conn


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = init_db()
    return _conn


def load_seed(hospital_id: str) -> None:
    global _base_rates, _hospital_id, _facility_id
    _hospital_id = hospital_id
    _facility_id = hospital_id.upper()

    conn = get_conn()
    path = _find_seed_path(hospital_id)
    data = json.loads(path.read_text())

    with _lock:
        conn.execute("DELETE FROM lots")
        conn.execute("DELETE FROM consumption_log")
        for lot in data["lots"]:
            conn.execute(
                "INSERT INTO lots (drug_code, batch_no, expiry, qty, status) "
                "VALUES (?, ?, ?, ?, 'active')",
                (lot["drug_code"], lot["batch_no"], lot["expiry"], lot["qty"]),
            )
        conn.commit()

    _base_rates = {}
    for drug_code, entries in data.get("consumption_last_30d", {}).items():
        if entries:
            total = sum(e["qty"] for e in entries)
            _base_rates[drug_code] = total / len(entries)
        else:
            _base_rates[drug_code] = 0.0


def get_base_rates() -> dict[str, float]:
    return dict(_base_rates)


def get_hospital_id() -> str:
    return _hospital_id


def get_facility_id() -> str:
    return _facility_id


def get_active_lots(drug_code: str) -> list[dict]:
    with _lock:
        rows = get_conn().execute(
            "SELECT drug_code, batch_no, expiry, qty FROM lots "
            "WHERE drug_code = ? AND status = 'active' AND qty > 0 "
            "ORDER BY expiry ASC",
            (drug_code,),
        ).fetchall()
        return [dict(r) for r in rows]


def decrement_lot(drug_code: str, batch_no: str, amount: int) -> None:
    with _lock:
        get_conn().execute(
            "UPDATE lots SET qty = MAX(0, qty - ?) "
            "WHERE drug_code = ? AND batch_no = ?",
            (amount, drug_code, batch_no),
        )
        get_conn().commit()


def expire_lots(today_str: str) -> None:
    with _lock:
        get_conn().execute(
            "UPDATE lots SET qty = 0, status = 'expired' "
            "WHERE expiry <= ? AND status = 'active'",
            (today_str,),
        )
        get_conn().commit()


def insert_consumption(
    date_str: str, drug_code: str, demanded: int, dispensed: int, stockout_qty: int
) -> None:
    with _lock:
        get_conn().execute(
            "INSERT INTO consumption_log (date, drug_code, demanded, dispensed, stockout_qty) "
            "VALUES (?, ?, ?, ?, ?)",
            (date_str, drug_code, demanded, dispensed, stockout_qty),
        )
        get_conn().commit()


def upsert_lot(
    drug_code: str, batch_no: str, expiry: str, qty: int, status: str = "active"
) -> None:
    with _lock:
        get_conn().execute(
            "INSERT INTO lots (drug_code, batch_no, expiry, qty, status) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (drug_code, batch_no) DO UPDATE "
            "SET qty = qty + EXCLUDED.qty, expiry = EXCLUDED.expiry, status = EXCLUDED.status",
            (drug_code, batch_no, expiry, qty, status),
        )
        get_conn().commit()


def get_all_lots() -> list[dict]:
    with _lock:
        rows = get_conn().execute(
            "SELECT drug_code, batch_no, expiry, qty, status "
            "FROM lots ORDER BY drug_code, expiry"
        ).fetchall()
        return [dict(r) for r in rows]


def get_consumption_log() -> list[dict]:
    with _lock:
        rows = get_conn().execute(
            "SELECT date, drug_code, demanded, dispensed, stockout_qty "
            "FROM consumption_log ORDER BY date, drug_code"
        ).fetchall()
        return [dict(r) for r in rows]


def get_lot_count() -> int:
    with _lock:
        row = get_conn().execute(
            "SELECT COUNT(*) as cnt FROM lots WHERE status = 'active' AND qty > 0"
        ).fetchone()
        return row["cnt"]


def get_total_stock() -> int:
    with _lock:
        row = get_conn().execute(
            "SELECT COALESCE(SUM(qty), 0) as total FROM lots WHERE status = 'active'"
        ).fetchone()
        return row["total"]


def reset(hospital_id: str) -> None:
    global _conn
    with _lock:
        if _conn:
            _conn.close()
        _conn = None
    init_db()
    load_seed(hospital_id)


def get_drug_codes() -> list[str]:
    return list(_base_rates.keys())
