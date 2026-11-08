"""API endpoint tests for ingest-ai."""
from __future__ import annotations

import asyncio
import os
import json
from datetime import date

import pytest

os.environ["USE_FIXTURES"] = "1"

from fastapi.testclient import TestClient
from app.main import app
from conftest import SAMPLE_FHIR, SAMPLE_CSV


@pytest.fixture(autouse=True)
def _keep_ingestion_tests_off_external_services(monkeypatch):
    async def no_genai(*args, **kwargs):
        return None

    async def no_gate(*args, **kwargs):
        from app.gate import GateResult
        return GateResult()

    monkeypatch.setattr("app.extraction.call_genai_extract", no_genai)
    monkeypatch.setattr("app.router.run_gate", no_gate)
    from app.router import _reports
    _reports.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("ok", "degraded")
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
    assert data["items"]
    assert data["items"][0]["drug_code"] == "INSULIN"
    assert data["items"][0]["qty"] == 20
    assert data["items"][0]["extraction_method"] == "deterministic_fallback"


def test_ingest_chat_push_returns_genai_extraction(client, monkeypatch):
    captured = {}

    async def fake_genai(raw_text, report_date, facility_code, candidates, **kwargs):
        captured["raw_text"] = raw_text
        captured["report_date"] = report_date
        captured["facility_code"] = facility_code
        captured["candidates"] = candidates
        return {
            "items": [{
                "raw_span": "insulin 20 vials",
                "drug_code": "INSULIN",
                "batch_no": "INS-001",
                "expiry": "2027-03-15",
                "qty": 20,
                "unit": "vial",
                "confidence": 0.95,
            }],
        }

    monkeypatch.setattr("app.extraction.call_genai_extract", fake_genai)
    response = client.post("/ingest/H3", json={
        "facility_id": "H3",
        "date": "2026-11-07",
        "format": "chat",
        "body": "insulin 20 vials",
    })

    assert response.status_code == 200
    data = response.json()
    assert captured["raw_text"] == "insulin 20 vials"
    assert captured["report_date"] == "2026-11-07"
    assert captured["facility_code"] == "H3"
    assert any(candidate["drug_code"] == "INSULIN" for candidate in captured["candidates"])
    assert data["extraction_method"] == "genai"
    assert data["items"] == [{
        "drug_name_raw": "insulin 20 vials",
        "drug_code": "INSULIN",
        "batch_no": "INS-001",
        "expiry": "2027-03-15",
        "qty": 20,
        "unit": "vial",
        "confidence": 0.95,
        "flags": [],
        "extraction_method": "genai",
    }]


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
    assert data["items"]
    assert data["items"][0]["drug_code"] == "INSULIN"
    assert data["items"][0]["qty"] == 50


def test_ingest_json_chat_push_extracts_only_message_body(client, monkeypatch):
    async def unavailable_genai(*args, **kwargs):
        from app.extraction import _extract_deterministic, scan_text_for_mentions
        text = args[0]
        return _extract_deterministic(
            text, scan_text_for_mentions(text), args[1],
        )

    monkeypatch.setattr("app.router.extract_from_text", unavailable_genai)
    response = client.post("/ingest/H3", json={
        "facility_id": "H3",
        "date": "2026-11-07",
        "format": "chat",
        "body": "ನಮಸ್ಕಾರ\n- insulin 20 vials, batch INS-001 exp 15/03",
    })
    data = response.json()

    assert response.status_code == 200
    assert data["raw_text"].startswith("ನಮಸ್ಕಾರ")
    assert "facility_id" not in data["raw_text"]
    assert data["reported_at"] == "2026-11-07"
    assert data["items"][0]["expiry"] == "2027-03-15"


def test_pull_run_uses_real_hospital_report_paths(client, monkeypatch):
    import httpx

    requested_urls = []

    class FakeResponse:
        status_code = 200
        text = "Facility Code,Drug Name,Batch No,Exp Date,Qty,Unit\n"

        def raise_for_status(self):
            return None

        def json(self):
            return SAMPLE_FHIR

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            requested_urls.append(url)
            return FakeResponse()

    async def process_report(facility_code, payload):
        return {
            "id": f"report-{facility_code}",
            "facility_code": facility_code,
            "items": [],
        }

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient())
    monkeypatch.setattr("app.router._process_report", process_report)

    response = client.post("/pull/run")

    assert response.status_code == 200
    assert response.json()["triggered"] == 2
    assert any(url.endswith("/fhir/InventoryReport") for url in requested_urls)
    assert "http://sim-hospital-h2:8101/export/stock.csv" in requested_urls


@pytest.mark.asyncio
async def test_demo_seed_runs_reports_through_extraction_and_is_idempotent(monkeypatch):
    monkeypatch.setattr("medbal_common.clock.today", lambda: date(2026, 11, 7))
    async def slow_no_genai(*args, **kwargs):
        await asyncio.sleep(0.01)
        return None

    monkeypatch.setattr("app.extraction.call_genai_extract", slow_no_genai)
    from app.router import _reports, seed_demo_reports
    first, second = await asyncio.gather(seed_demo_reports(), seed_demo_reports())

    assert first["triggered"] == 2
    assert all(report["items"] > 0 for report in first["reports"])
    assert all(
        report["extraction_method"] == "deterministic_fallback"
        for report in first["reports"]
    )
    assert second["reports"] == first["reports"]
    assert len(_reports) == 2


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
