"""Tests for P17: custody scan, HMAC verification, state machine, deviation detection, audit tamper/restore."""
from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import text

from medbal_common.db import session_scope
from medbal_common import audit


def _make_token(order_id: str, secret: str = "dev-secret") -> str:
    return hmac_mod.new(secret.encode(), order_id.encode(), hashlib.sha256).hexdigest()


@pytest.fixture
def seed_order(db_engine):
    """Create a minimal approved order for custody tests."""
    with db_engine.connect() as conn:
        conn.execute(text("DELETE FROM custody_event"))
        conn.execute(text("DELETE FROM transfer_order"))
        conn.execute(text("DELETE FROM plan_run"))
        conn.execute(text("DELETE FROM audit_log"))
        conn.execute(text("DELETE FROM lot"))
        conn.execute(text("DELETE FROM route"))
        conn.execute(text("DELETE FROM drug"))
        conn.execute(text("DELETE FROM facility"))

        conn.execute(text(
            "INSERT INTO facility VALUES ('W0','SIM-Warehouse','WH',12.97,77.59,1,NULL,'fhir','en','South',datetime('now'))"
        ))
        conn.execute(text(
            "INSERT INTO facility VALUES ('H1','SIM-DH Jayanagar','DH',12.925,77.593,1,NULL,'fhir','en','South',datetime('now'))"
        ))
        conn.execute(text(
            "INSERT INTO drug VALUES ('PCM','Paracetamol 500mg','E','tablet',10,0,NULL,NULL,0,30,0.50,datetime('now'))"
        ))
        conn.execute(text(
            "INSERT INTO drug VALUES ('INSULIN','Insulin Human 40 IU/ml','V','vial',1,1,2.0,8.0,0,60,45.00,datetime('now'))"
        ))
        conn.execute(text(
            "INSERT INTO route (src_facility_id,dst_facility_id,distance_km,transit_hours,cold_capable,cost_ambient_inr,cost_cold_inr) "
            "VALUES ('W0','H1',15.0,0.5,1,100.0,200.0)"
        ))
        conn.execute(text(
            "INSERT INTO plan_run VALUES ('plan-t1','live','sa',NULL,NULL,NULL,NULL,1,NULL,NULL,NULL,NULL,datetime('now'))"
        ))

        token = _make_token("ORD-T1")
        conn.execute(text(
            "INSERT INTO transfer_order (id, dta_number, plan_run_id, src_facility_id, "
            "dst_facility_id, drug_code, drug_name, batch_no, qty, usable, score, "
            "status, temperature_req, qr_token) "
            "VALUES ('ORD-T1', 'DTA/BLR-U/2026/000099', 'plan-t1', 'W0', 'H1', "
            "'PCM', 'Paracetamol 500mg', 'B-PCM-001', 100, 100, 0.9, "
            "'approved', 'ambient', :token)"
        ), {"token": token})

        conn.execute(text(
            "INSERT INTO lot (facility_id, drug_code, batch_no, expiry, qty) "
            "VALUES ('W0', 'PCM', 'B-PCM-001', '2027-04-15', 500)"
        ))

        conn.commit()
    return token


@pytest.fixture
def seed_cold_order(db_engine, seed_order):
    """Add a cold-chain order for excursion testing."""
    with db_engine.connect() as conn:
        token = _make_token("ORD-T2")
        conn.execute(text(
            "INSERT INTO transfer_order (id, dta_number, plan_run_id, src_facility_id, "
            "dst_facility_id, drug_code, drug_name, batch_no, qty, usable, score, "
            "status, temperature_req, vehicle_id, qr_token, dispatched_at) "
            "VALUES ('ORD-T2', 'DTA/BLR-U/2026/000100', 'plan-t1', 'W0', 'H1', "
            "'INSULIN', 'Insulin Human 40 IU/ml', 'B-INS-001', 50, 50, 0.85, "
            "'dispatched', 'cold_chain', 'CV-01', :token, :dispatched_at)"
        ), {"token": token, "dispatched_at": datetime.now(timezone.utc).isoformat()})
        conn.commit()
    return token


# ── State machine tests ──────────────────────────────────────────

@patch("medbal_common.bus.publish")
def test_dispatch_from_approved(mock_pub, seed_order):
    from app.routers.custody import scan_custody, ScanRequest
    import asyncio

    req = ScanRequest(token=seed_order, event="dispatch", actor="pharmacist")
    result = asyncio.get_event_loop().run_until_complete(scan_custody(req))
    body = json.loads(result.body)

    assert body["event"] == "dispatch"
    assert body["status"] == "dispatched"
    assert body["order_id"] == "ORD-T1"
    assert body["qty"] == 100


@patch("medbal_common.bus.publish")
def test_cannot_dispatch_from_proposed(mock_pub, db_engine):
    """Dispatch requires status=approved, not proposed."""
    with db_engine.connect() as conn:
        conn.execute(text("DELETE FROM custody_event"))
        conn.execute(text("DELETE FROM transfer_order"))
        conn.execute(text("DELETE FROM plan_run"))
        conn.execute(text("DELETE FROM audit_log"))
        conn.execute(text("DELETE FROM facility"))
        conn.execute(text("DELETE FROM drug"))

        conn.execute(text(
            "INSERT INTO facility VALUES ('W0','SIM-Warehouse','WH',12.97,77.59,1,NULL,'fhir','en','S',datetime('now'))"
        ))
        conn.execute(text(
            "INSERT INTO drug VALUES ('PCM','Paracetamol 500mg','E','tablet',10,0,NULL,NULL,0,30,0.50,datetime('now'))"
        ))
        conn.execute(text(
            "INSERT INTO plan_run VALUES ('plan-x','live','sa',NULL,NULL,NULL,NULL,0,NULL,NULL,NULL,NULL,datetime('now'))"
        ))
        token = _make_token("ORD-X1")
        conn.execute(text(
            "INSERT INTO transfer_order (id, dta_number, plan_run_id, src_facility_id, "
            "dst_facility_id, drug_code, drug_name, batch_no, qty, usable, "
            "status, temperature_req, qr_token) "
            "VALUES ('ORD-X1', 'DTA/BLR-U/2026/000200', 'plan-x', 'W0', 'W0', "
            "'PCM', 'Paracetamol 500mg', 'B1', 10, 10, 'proposed', 'ambient', :t)"
        ), {"t": token})
        conn.commit()

    from app.routers.custody import scan_custody, ScanRequest
    import asyncio

    req = ScanRequest(token=token, event="dispatch", actor="test")
    with pytest.raises(Exception) as exc_info:
        asyncio.get_event_loop().run_until_complete(scan_custody(req))
    assert "409" in str(exc_info.value.status_code) or "Cannot dispatch" in str(exc_info.value.detail)


@patch("medbal_common.bus.publish")
def test_full_lifecycle(mock_pub, seed_order):
    """approved → dispatch → receive → consume."""
    from app.routers.custody import scan_custody, ScanRequest
    import asyncio

    loop = asyncio.get_event_loop()

    r1 = loop.run_until_complete(scan_custody(
        ScanRequest(token=seed_order, event="dispatch", actor="pharmacist")
    ))
    assert json.loads(r1.body)["status"] == "dispatched"

    r2 = loop.run_until_complete(scan_custody(
        ScanRequest(token=seed_order, event="receive", qty=100, actor="receiver")
    ))
    assert json.loads(r2.body)["status"] == "received"

    r3 = loop.run_until_complete(scan_custody(
        ScanRequest(token=seed_order, event="consume", actor="nurse")
    ))
    assert json.loads(r3.body)["status"] == "consumed"


@patch("medbal_common.bus.publish")
def test_cannot_receive_from_approved(mock_pub, seed_order):
    """Cannot skip dispatch and go straight to receive."""
    from app.routers.custody import scan_custody, ScanRequest
    import asyncio

    req = ScanRequest(token=seed_order, event="receive", actor="test")
    with pytest.raises(Exception) as exc_info:
        asyncio.get_event_loop().run_until_complete(scan_custody(req))
    assert "409" in str(exc_info.value.status_code) or "Cannot receive" in str(exc_info.value.detail)


# ── HMAC rejection ───────────────────────────────────────────────

@patch("medbal_common.bus.publish")
def test_invalid_hmac_rejected(mock_pub, seed_order):
    from app.routers.custody import scan_custody, ScanRequest
    import asyncio

    bad_token = "0" * 64
    req = ScanRequest(token=bad_token, event="dispatch", actor="test")
    with pytest.raises(Exception) as exc_info:
        asyncio.get_event_loop().run_until_complete(scan_custody(req))
    assert "403" in str(exc_info.value.status_code) or "404" in str(exc_info.value.status_code)


# ── Deviation detection ──────────────────────────────────────────

@patch("medbal_common.bus.publish")
def test_qty_mismatch_deviation(mock_pub, seed_order):
    """Receiving fewer units than dispatched triggers qty_mismatch."""
    from app.routers.custody import scan_custody, ScanRequest
    import asyncio

    loop = asyncio.get_event_loop()

    loop.run_until_complete(scan_custody(
        ScanRequest(token=seed_order, event="dispatch", actor="pharmacist")
    ))

    r = loop.run_until_complete(scan_custody(
        ScanRequest(token=seed_order, event="receive", qty=90, actor="receiver")
    ))
    body = json.loads(r.body)
    assert "deviations" in body
    devs = body["deviations"]
    assert any(d["type"] == "qty_mismatch" for d in devs)
    mismatch = next(d for d in devs if d["type"] == "qty_mismatch")
    assert mismatch["expected"] == 100
    assert mismatch["actual"] == 90


# ── Custody chain query ──────────────────────────────────────────

@patch("medbal_common.bus.publish")
def test_custody_chain_populated(mock_pub, seed_order):
    from app.routers.custody import scan_custody, ScanRequest
    import asyncio

    loop = asyncio.get_event_loop()
    loop.run_until_complete(scan_custody(
        ScanRequest(token=seed_order, event="dispatch", actor="pharmacist")
    ))
    loop.run_until_complete(scan_custody(
        ScanRequest(token=seed_order, event="receive", qty=100, actor="receiver")
    ))

    with session_scope() as s:
        from app.queries import get_custody_events
        events = get_custody_events(s, "ORD-T1")

    assert len(events) == 2
    assert events[0]["event_type"] == "dispatch"
    assert events[1]["event_type"] == "receive"


# ── Audit verify / tamper / restore ──────────────────────────────

@patch("medbal_common.bus.publish")
def test_audit_verify_ok_after_scan(mock_pub, seed_order):
    from app.routers.custody import scan_custody, ScanRequest
    import asyncio

    asyncio.get_event_loop().run_until_complete(scan_custody(
        ScanRequest(token=seed_order, event="dispatch", actor="pharmacist")
    ))

    with session_scope() as s:
        result = audit.verify(s)
    assert result["ok"] is True


def test_audit_tamper_breaks_verify(seed_order):
    """Tampering breaks the hash chain; restore fixes it."""
    with session_scope() as s:
        seq = audit.append(s, "test", "test.action", "test", "T1", {"data": "original"})

    with session_scope() as s:
        result = audit.verify(s)
    assert result["ok"] is True

    from app.queries import tamper_audit_row, restore_audit_row
    with session_scope() as s:
        tamper_result = tamper_audit_row(s, seq)
    assert tamper_result["tampered"] is True

    with session_scope() as s:
        result = audit.verify(s)
    assert result["ok"] is False

    with session_scope() as s:
        restore_audit_row(s, seq, tamper_result["original_payload"])

    with session_scope() as s:
        result = audit.verify(s)
    assert result["ok"] is True


# ── API integration ──────────────────────────────────────────────

@patch("medbal_common.bus.publish")
def test_api_custody_scan_dispatch(mock_pub, seed_order):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.post("/custody/scan", json={
        "token": seed_order,
        "event": "dispatch",
        "actor": "pharmacist",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "dispatched"


@patch("medbal_common.bus.publish")
def test_api_custody_scan_invalid_token(mock_pub, seed_order):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.post("/custody/scan", json={
        "token": "bad" * 21 + "x",
        "event": "dispatch",
        "actor": "test",
    })
    assert resp.status_code in (403, 404)


@patch("medbal_common.bus.publish")
def test_api_audit_tamper_restore(mock_pub, seed_order):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    client.post("/custody/scan", json={
        "token": seed_order, "event": "dispatch", "actor": "test",
    })

    verify1 = client.get("/audit/verify")
    assert verify1.json()["ok"] is True

    tamper = client.post("/admin/tamper-demo", json={})
    assert tamper.status_code == 200

    verify2 = client.get("/audit/verify")
    assert verify2.json()["ok"] is False

    restore = client.post("/admin/restore-demo", json={})
    assert restore.status_code == 200

    verify3 = client.get("/audit/verify")
    assert verify3.json()["ok"] is True


@patch("medbal_common.bus.publish")
def test_api_custody_chain(mock_pub, seed_order):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    client.post("/custody/scan", json={
        "token": seed_order, "event": "dispatch", "actor": "pharmacist",
    })

    resp = client.get("/custody/ORD-T1")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "dispatch"
