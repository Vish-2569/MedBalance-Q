"""API endpoint integration tests via TestClient."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

svc_path = str(Path(__file__).resolve().parents[1])
if svc_path not in sys.path:
    sys.path.insert(0, svc_path)

from fastapi.testclient import TestClient
from app.main import app

import medbal_common.db as db_mod


@pytest.fixture
def client(db_engine):
    db_mod._engine = db_engine
    db_mod._session_factory = db_mod.get_session_factory(db_engine)
    return TestClient(app, raise_server_exceptions=False)


def test_facilities(client, seed_data):
    r = client.get("/facilities")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) >= 3
    w0 = next(f for f in data if f["id"] == "W0")
    assert w0["type"] == "warehouse"
    h1 = next(f for f in data if f["id"] == "H1")
    assert h1["type"] == "hospital"
    assert h1["cold_storage"] is True


def test_drugs(client, seed_data):
    r = client.get("/drugs")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) >= 2
    insulin = next(d for d in data if d["code"] == "INSULIN")
    assert insulin["cold_chain"] is True
    assert insulin["ven"] == "V"


def test_routes(client, seed_data):
    r = client.get("/routes")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) >= 1
    route = data[0]
    assert "cold_chain" in route
    assert "distance_km" in route


def test_vehicles(client, seed_data):
    r = client.get("/vehicles")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) >= 1


def test_lots(client, seed_data):
    r = client.get("/lots")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) >= 3


def test_lots_filter(client, seed_data):
    r = client.get("/lots?facility=H4&drug=INSULIN")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) >= 1
    assert all(l["facility_id"] == "H4" for l in data)
    assert all(l["drug_code"] == "INSULIN" for l in data)


def test_positions(client, seed_data):
    r = client.get("/positions")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) >= 3
    for pos in data:
        assert "facility_id" in pos
        assert "drug_code" in pos
        assert "effective_stock" in pos
        assert "shortage" in pos
        assert pos["effective_stock"] >= 0


def test_snapshot(client, seed_data):
    r = client.get("/snapshot")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "facilities" in data
    assert "drugs" in data
    assert "lots" in data
    assert "positions" in data
    assert "snapshot_hash" in data
    assert len(data["positions"]) >= 1


def test_audit_verify(client, seed_data):
    r = client.get("/audit/verify")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "ok" in data
    assert "entries" in data


def test_custody_scan_requires_fields(client):
    r = client.post("/custody/scan", json={})
    assert r.status_code == 422


def test_order_not_found(client, seed_data):
    r = client.get("/orders/nonexistent")
    assert r.status_code == 404
