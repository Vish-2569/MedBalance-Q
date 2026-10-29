"""Tests for narration, numeric firewall, and PDF generation (P15)."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import prompt_registry
from app.cache import LLMCache
from app.firewall import check_narration, extract_values, _deterministic_narration
from app.llm_service import LLMService
from app.narration import narrate_order, narrate_credit_memo
from app.pdf_gen import (
    generate_dta_pdf,
    generate_coldchain_log_pdf,
    generate_credit_memo_pdf,
    get_qr_data_uri,
)
from app.providers import FakeProvider

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


@pytest.fixture(autouse=True)
def _load_prompts():
    prompt_registry.load_all(PROMPTS_DIR)


SAMPLE_ORDER_FACTS = {
    "order_id": "ORD-001",
    "drug_name": "Paracetamol 500mg",
    "drug_code": "PCM500",
    "qty": 1000,
    "unit": "tablets",
    "batch_no": "B2026-101",
    "expiry": "2027-03-15",
    "src_facility": "SIM-District-H1",
    "src_facility_id": "H1",
    "dst_facility": "SIM-PHC-H3",
    "dst_facility_id": "H3",
    "usable": 950,
    "src_rate": 40,
    "dst_rate": 60,
    "shortage_before": 500,
    "shortage_after": 0,
    "expiry_avoided": 1000,
    "top_alternative": "SIM-PHC-H4",
}

SAMPLE_ORDER = {
    "id": "ORD-001",
    "dta_number": "DTA/BLR-U/2026/000001",
    "plan_id": "PLAN-001",
    "src_facility_id": "H1",
    "src_facility_name": "SIM-District-H1",
    "dst_facility_id": "H3",
    "dst_facility_name": "SIM-PHC-H3",
    "drug_code": "PCM500",
    "drug_name": "Paracetamol 500mg",
    "batch_no": "B2026-101",
    "expiry": "2027-03-15",
    "qty": 1000,
    "usable": 950,
    "score": 0.85,
    "status": "approved",
    "temperature_req": "ambient",
    "qr_token": "abc123tokenvalue",
    "created_at": "2026-10-30",
    "approved_by": "Dr. Demo",
    "approved_at": "2026-10-30T10:00:00",
    "audit_hash": "sha256:abcdef1234567890",
}


# ── Firewall: extract_values ──────────────────────────────────────

def test_extract_currency():
    vals = extract_values("Total value ₹1,50,000 transferred.")
    currencies = [v for v in vals if v["type"] == "currency"]
    assert len(currencies) == 1
    assert currencies[0]["value"] == 150000.0


def test_extract_percentage():
    vals = extract_values("Reduction of 45.2% achieved.")
    pcts = [v for v in vals if v["type"] == "percentage"]
    assert len(pcts) == 1
    assert pcts[0]["value"] == 45.2


def test_extract_iso_date():
    vals = extract_values("Expiry is 2027-03-15.")
    dates = [v for v in vals if v["type"] == "date"]
    assert any(d["value"] == "2027-03-15" for d in dates)


def test_extract_plain_number():
    vals = extract_values("Transfer 1000 tablets.")
    nums = [v for v in vals if v["type"] == "number"]
    assert any(n["value"] == 1000.0 for n in nums)


# ── Firewall: check_narration ─────────────────────────────────────

def test_firewall_passes_correct_narration():
    narration = (
        "Transfer 1000 tablets of Paracetamol 500mg from SIM-District-H1 "
        "to SIM-PHC-H3. 950 tablets usable before expiry 2027-03-15. "
        "Reduces shortage from 500 to 0."
    )
    result = check_narration(narration, SAMPLE_ORDER_FACTS)
    assert result["grounding_ok"] is True
    assert result["narration"] == narration
    assert result["mismatches"] == []


def test_firewall_catches_injected_wrong_number():
    narration = (
        "Transfer 9999 tablets of Paracetamol 500mg from SIM-District-H1 "
        "to SIM-PHC-H3. 950 usable before expiry 2027-03-15."
    )
    result = check_narration(narration, SAMPLE_ORDER_FACTS)
    assert result["grounding_ok"] is False
    assert len(result["mismatches"]) >= 1
    assert "9999" in result["mismatches"][0]["raw"]
    assert "Transfer" in result["narration"]


def test_firewall_catches_wrong_date():
    narration = (
        "Transfer 1000 tablets. Expires 2099-12-31."
    )
    result = check_narration(narration, SAMPLE_ORDER_FACTS)
    assert result["grounding_ok"] is False
    assert any(m["type"] == "date" for m in result["mismatches"])


def test_deterministic_narration_contains_facts():
    text = _deterministic_narration(SAMPLE_ORDER_FACTS)
    assert "1000" in text
    assert "Paracetamol" in text
    assert "SIM-District-H1" in text
    assert "SIM-PHC-H3" in text
    assert "950" in text
    assert "500" in text


# ── Narration service ─────────────────────────────────────────────

def test_narrate_order_with_fake_provider():
    provider = FakeProvider(responses=[{
        "narration": (
            "Transfer 1000 tablets of Paracetamol 500mg from SIM-District-H1 "
            "to SIM-PHC-H3. 950 usable before expiry 2027-03-15. "
            "Reduces shortage from 500 to 0."
        )
    }])
    cache = LLMCache(redis_client=None)
    svc = LLMService(provider=provider, cache=cache)

    result = asyncio.get_event_loop().run_until_complete(
        narrate_order(svc, SAMPLE_ORDER_FACTS)
    )
    assert result["grounding_ok"] is True
    assert result["fallback"] is False
    assert "1000" in result["narration"]


def test_narrate_order_fallback_on_llm_failure():
    provider = FakeProvider(responses=[])
    cache = LLMCache(redis_client=None)
    svc = LLMService(provider=provider, cache=cache)

    result = asyncio.get_event_loop().run_until_complete(
        narrate_order(svc, SAMPLE_ORDER_FACTS)
    )
    assert result["fallback"] is True
    assert result["grounding_ok"] is True
    assert "1000" in result["narration"]


def test_narrate_credit_memo():
    provider = FakeProvider(responses=[{
        "paragraph": (
            "SIM-District-H1 contributed 1000 units of medicines "
            "valued at ₹5000 redistributed to 1 receiving facility."
        )
    }])
    cache = LLMCache(redis_client=None)
    svc = LLMService(provider=provider, cache=cache)

    memo_facts = {
        "donor_facility": "SIM-District-H1",
        "total_units": 1000,
        "value_inr": 5000,
        "drugs_summary": "Paracetamol 500mg",
        "transfer_count": 1,
        "receivers": "SIM-PHC-H3",
        "unit": "units",
    }

    result = asyncio.get_event_loop().run_until_complete(
        narrate_credit_memo(svc, memo_facts)
    )
    assert "paragraph" in result
    assert result["grounding_ok"] is True


# ── PDF generation ────────────────────────────────────────────────

def test_dta_pdf_renders():
    pdf_bytes = generate_dta_pdf(SAMPLE_ORDER)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 100
    if pdf_bytes[:4] == b"<!DO":
        html = pdf_bytes.decode("utf-8")
        assert "DRUG TRANSFER ADVICE" in html
        assert "DTA/BLR-U/2026/000001" in html
        assert "Paracetamol" in html
        assert "Synthetic demo data" in html


def test_dta_pdf_never_says_form_19():
    pdf_bytes = generate_dta_pdf(SAMPLE_ORDER)
    text = pdf_bytes.decode("utf-8", errors="ignore")
    assert "Form 19" not in text
    assert "form 19" not in text.lower()


def test_dta_pdf_near_expiry_flag():
    order = {**SAMPLE_ORDER, "expiry": "2026-12-01"}
    pdf_bytes = generate_dta_pdf(order)
    text = pdf_bytes.decode("utf-8", errors="ignore")
    assert "Near" in text


def test_coldchain_log_pdf_renders():
    order = {**SAMPLE_ORDER, "temperature_req": "cold_chain", "vehicle_id": "VH-COLD-01"}
    readings = [
        {"timestamp": "2026-10-30T08:00:00", "temp_c": 4.2, "humidity": 45},
        {"timestamp": "2026-10-30T08:05:00", "temp_c": 9.5, "humidity": 44},
        {"timestamp": "2026-10-30T08:10:00", "temp_c": 4.1, "humidity": 46},
    ]
    pdf_bytes = generate_coldchain_log_pdf(order, readings)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 100
    if pdf_bytes[:4] == b"<!DO":
        html = pdf_bytes.decode("utf-8")
        assert "COLD-CHAIN CONSIGNMENT LOG" in html
        assert "BREACH" in html


def test_credit_memo_pdf_renders():
    donor = {"id": "H1", "name": "SIM-District-H1"}
    items = [
        {"drug_name": "Paracetamol 500mg", "qty": 1000, "unit": "tablets",
         "dst_facility": "SIM-PHC-H3", "value_inr": 5000},
    ]
    pdf_bytes = generate_credit_memo_pdf(donor, items, paragraph="Test paragraph.", plan_id="PLAN-001")
    assert pdf_bytes is not None
    if pdf_bytes[:4] == b"<!DO":
        html = pdf_bytes.decode("utf-8")
        assert "DONOR CREDIT MEMO" in html
        assert "SIM-District-H1" in html
        assert "5000" in html


# ── QR code ───────────────────────────────────────────────────────

def test_qr_generates_data_uri():
    uri = get_qr_data_uri("http://localhost:8080/api/core/scan/abc123")
    if uri:
        assert uri.startswith("data:image/png;base64,")
        import base64
        b64 = uri.split(",", 1)[1]
        decoded = base64.b64decode(b64)
        assert decoded[:4] == b"\x89PNG"


def test_qr_decodes_to_scan_url():
    scan_url = "http://localhost:8080/api/core/scan/abc123tokenvalue"
    uri = get_qr_data_uri(scan_url)
    if uri:
        import base64
        import io
        b64 = uri.split(",", 1)[1]
        img_bytes = base64.b64decode(b64)
        try:
            from PIL import Image
            from pyzbar.pyzbar import decode as qr_decode
            img = Image.open(io.BytesIO(img_bytes))
            results = qr_decode(img)
            assert len(results) >= 1
            assert results[0].data.decode() == scan_url
        except ImportError:
            import qrcode
            assert len(img_bytes) > 100


# ── API endpoints ─────────────────────────────────────────────────

def test_api_narrate_single():
    from fastapi.testclient import TestClient

    os.environ["LLM_PROVIDER"] = "fake"
    os.environ["DEMO_MODE"] = "live"

    from app.main import create_app
    test_app = create_app()
    client = TestClient(test_app)

    resp = client.post("/narrate/ORD-001", json={
        "order_facts": SAMPLE_ORDER_FACTS,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "narration" in data
    assert data["order_id"] == "ORD-001"


def test_api_narrate_batch():
    from fastapi.testclient import TestClient

    os.environ["LLM_PROVIDER"] = "fake"
    os.environ["DEMO_MODE"] = "live"

    from app.main import create_app
    test_app = create_app()
    client = TestClient(test_app)

    resp = client.post("/narrate/batch", json={
        "orders": [SAMPLE_ORDER_FACTS],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "narrations" in data
    assert len(data["narrations"]) == 1
