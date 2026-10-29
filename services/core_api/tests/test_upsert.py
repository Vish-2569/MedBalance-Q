"""Test lot upsert idempotency and audit trail."""
from __future__ import annotations

from medbal_common.db import session_scope
from medbal_common import audit

from app.queries import upsert_lot, list_lots


def test_upsert_creates_new_lot(db_engine, seed_data):
    with session_scope() as s:
        old_qty, new_qty = upsert_lot(s, {
            "facility_id": "H1",
            "drug_code": "PCM",
            "batch_no": "B-NEW-001",
            "expiry": "2027-06-01",
            "qty": 200,
        })
    assert old_qty == 0
    assert new_qty == 200

    with session_scope() as s:
        lots = list_lots(s, facility="H1", drug="PCM")
    batch_nos = [l["batch_no"] for l in lots]
    assert "B-NEW-001" in batch_nos


def test_upsert_updates_existing_lot(db_engine, seed_data):
    with session_scope() as s:
        old_qty, new_qty = upsert_lot(s, {
            "facility_id": "H4",
            "drug_code": "INSULIN",
            "batch_no": "B-INS-H4-001",
            "expiry": "2026-11-19",
            "qty": 45,
        })
    assert old_qty == 50
    assert new_qty == 45

    with session_scope() as s:
        lots = list_lots(s, facility="H4", drug="INSULIN")
    lot = next(l for l in lots if l["batch_no"] == "B-INS-H4-001")
    assert lot["qty"] == 45


def test_upsert_idempotent(db_engine, seed_data):
    lot_data = {
        "facility_id": "H4",
        "drug_code": "INSULIN",
        "batch_no": "B-INS-H4-001",
        "expiry": "2026-11-19",
        "qty": 50,
    }
    with session_scope() as s:
        upsert_lot(s, lot_data)
    with session_scope() as s:
        upsert_lot(s, lot_data)
    with session_scope() as s:
        lots = list_lots(s, facility="H4", drug="INSULIN")
    lot = next(l for l in lots if l["batch_no"] == "B-INS-H4-001")
    assert lot["qty"] == 50


def test_upsert_with_audit(db_engine, seed_data):
    with session_scope() as s:
        upsert_lot(s, {
            "facility_id": "H1",
            "drug_code": "PCM",
            "batch_no": "B-PCM-AUDIT-TEST",
            "expiry": "2027-06-01",
            "qty": 100,
        })
        audit.append(s, "system", "lot.upsert", "lot",
                     "H1:PCM:B-PCM-AUDIT-TEST", {"old_qty": 0, "new_qty": 100})

    with session_scope() as s:
        result = audit.verify(s)
    assert result["ok"] is True
