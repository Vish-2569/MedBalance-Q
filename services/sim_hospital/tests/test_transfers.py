"""Transfer endpoint tests via TestClient."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import stock_db
from app.routers import state, transfers

_app = FastAPI()
_app.include_router(transfers.router)
_app.include_router(state.router)


def _client():
    return TestClient(_app, raise_server_exceptions=False)


def test_outbound_decrements():
    conn = stock_db.get_conn()
    conn.execute("DELETE FROM lots")
    conn.execute(
        "INSERT INTO lots VALUES ('PCM','B1','2027-01-01',100,'active')"
    )
    conn.commit()
    stock_db._facility_id = "H1"
    stock_db._hospital_id = "h1"

    client = _client()
    resp = client.post(
        "/transfers/outbound",
        json={
            "order_id": "ORD-001",
            "items": [
                {"drug_code": "PCM", "batch_no": "B1", "qty": 30}
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["dispatched"] == 1

    lots = stock_db.get_active_lots("PCM")
    assert lots[0]["qty"] == 70


def test_inbound_creates_lot():
    conn = stock_db.get_conn()
    conn.execute("DELETE FROM lots")
    conn.commit()
    stock_db._facility_id = "H1"
    stock_db._hospital_id = "h1"

    client = _client()
    resp = client.post(
        "/transfers/inbound",
        json={
            "order_id": "ORD-002",
            "items": [
                {
                    "drug_code": "AMOX",
                    "batch_no": "B-NEW",
                    "qty": 200,
                    "expiry": "2027-06-01",
                }
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 1

    lots = stock_db.get_active_lots("AMOX")
    assert len(lots) == 1
    assert lots[0]["qty"] == 200


def test_outbound_insufficient():
    conn = stock_db.get_conn()
    conn.execute("DELETE FROM lots")
    conn.execute(
        "INSERT INTO lots VALUES ('PCM','B1','2027-01-01',10,'active')"
    )
    conn.commit()
    stock_db._facility_id = "H1"
    stock_db._hospital_id = "h1"

    client = _client()
    resp = client.post(
        "/transfers/outbound",
        json={
            "order_id": "ORD-003",
            "items": [
                {"drug_code": "PCM", "batch_no": "B1", "qty": 50}
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["dispatched"] == 0
