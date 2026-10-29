"""API endpoint tests for ingest-ai."""
from __future__ import annotations

import os
import json

import pytest

os.environ["USE_FIXTURES"] = "1"

from fastapi.testclient import TestClient
from app.main import app
from conftest import SAMPLE_FHIR, SAMPLE_CSV


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["service"] == "ingest-ai"


def test_ingest_fhir(client):
    resp = client.post(
        "/ingest/H1",
        json=SAMPLE_FHIR,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["facility_code"] == "H1"
    assert data["format"] == "fhir"
    assert len(data["items"]) == 2
    assert data["items"][0]["drug_code"] == "INSULIN"


def test_ingest_csv(client):
    resp = client.post(
        "/ingest/H2",
        content=SAMPLE_CSV,
        headers={"content-type": "text/csv"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["facility_code"] == "H2"
    assert data["format"] == "csv"
    assert len(data["items"]) == 3


def test_ingest_chat_push(client):
    msg = "ಇನ್ಸುಲಿನ್ 40IU - 20 vials"
    resp = client.post(
        "/ingest/H3",
        content=msg,
        headers={"content-type": "text/plain"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "chat"
    assert data["raw_text"] == msg
    assert data["items"] == []


def test_ingest_text_push(client):
    msg = "Insulin 50 vials batch INS-2026-001 exp Mar 2027"
    resp = client.post(
        "/ingest/H4",
        content=msg,
        headers={"content-type": "text/plain"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "text"
    assert data["raw_text"] == msg


def test_ingest_unknown_facility(client):
    resp = client.post("/ingest/H99", json={})
    assert resp.status_code == 400


def test_reports_list(client):
    client.post("/ingest/H3", content="test", headers={"content-type": "text/plain"})
    resp = client.get("/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_reports_filter_by_facility(client):
    from app.router import _reports
    _reports.clear()
    client.post("/ingest/H3", content="a", headers={"content-type": "text/plain"})
    client.post("/ingest/H4", content="b", headers={"content-type": "text/plain"})
    resp_h3 = client.get("/reports?facility=H3")
    resp_h4 = client.get("/reports?facility=H4")
    h3_data = resp_h3.json()
    h4_data = resp_h4.json()
    assert all(r["facility_code"] == "H3" for r in h3_data)
    assert all(r["facility_code"] == "H4" for r in h4_data)
    assert len(h3_data) == 1
    assert len(h4_data) == 1
