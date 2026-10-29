"""Tests for LLM-based extraction pipeline."""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.extraction import (
    scan_text_for_mentions,
    validate_extraction,
    extract_from_text,
    _resolve_date,
    _normalize_unit,
)
from app.grounding import reload_index


@pytest.fixture(autouse=True)
def fresh_index():
    reload_index()
    yield
    reload_index()


# ---------------------------------------------------------------------------
# scan_text_for_mentions
# ---------------------------------------------------------------------------

class TestScanText:
    def test_finds_kannada_mentions(self):
        text = "ಇನ್ಸುಲಿನ್ 40IU - 20 vials, ಪ್ಯಾರಸಿಟಮಾಲ್ 500 - 100 tabs"
        mentions = scan_text_for_mentions(text)
        codes = {m["drug_code"] for m in mentions}
        assert "INSULIN" in codes
        assert "PCM" in codes

    def test_finds_english_typos(self):
        text = "inzulin 50 vials batch INS-001 exp Mar 2027"
        mentions = scan_text_for_mentions(text)
        codes = {m["drug_code"] for m in mentions}
        assert "INSULIN" in codes

    def test_finds_mixed_mentions(self):
        text = "ORS 200 sachets, amoxy 500 cap 50 pcs"
        mentions = scan_text_for_mentions(text)
        codes = {m["drug_code"] for m in mentions}
        assert "ORS" in codes
        assert "AMOX" in codes

    def test_deduplicates_by_code(self):
        text = "insulin insulin insulin"
        mentions = scan_text_for_mentions(text)
        codes = [m["drug_code"] for m in mentions]
        assert codes.count("INSULIN") == 1

    def test_empty_text_returns_empty(self):
        assert scan_text_for_mentions("") == []

    def test_no_drugs_returns_empty(self):
        text = "hello this is a general message with no drug names"
        mentions = scan_text_for_mentions(text)
        assert len(mentions) == 0


# ---------------------------------------------------------------------------
# validate_extraction
# ---------------------------------------------------------------------------

class TestValidateExtraction:
    CANDIDATES = [
        {"mention": "ಇನ್ಸುಲಿನ್", "drug_code": "INSULIN", "drug_name": "Insulin Human 40 IU/ml", "score": 100},
        {"mention": "ಪ್ಯಾರಸಿಟಮಾಲ್", "drug_code": "PCM", "drug_name": "Paracetamol 500mg", "score": 100},
    ]

    def test_good_extraction(self):
        raw_items = [
            {"raw_span": "ಇನ್ಸುಲಿನ್ 40IU - 20 vials", "drug_code": "INSULIN",
             "batch_no": "INS-001", "expiry": "2027-03-15", "qty": 20, "unit": "vial",
             "confidence": 0.95},
        ]
        items = validate_extraction(raw_items, self.CANDIDATES, "2026-10-01")
        assert len(items) == 1
        assert items[0].drug_code == "INSULIN"
        assert items[0].qty == 20
        assert items[0].expiry == "2027-03-15"
        assert items[0].unit == "vial"
        assert items[0].flags == []

    def test_bad_qty_zero(self):
        raw_items = [
            {"raw_span": "insulin", "drug_code": "INSULIN", "qty": 0,
             "confidence": 0.5},
        ]
        items = validate_extraction(raw_items, self.CANDIDATES, "2026-10-01")
        assert "invalid_qty" in items[0].flags

    def test_bad_qty_negative(self):
        raw_items = [
            {"raw_span": "insulin", "drug_code": "INSULIN", "qty": -5,
             "confidence": 0.5},
        ]
        items = validate_extraction(raw_items, self.CANDIDATES, "2026-10-01")
        assert "invalid_qty" in items[0].flags

    def test_unknown_drug_code(self):
        raw_items = [
            {"raw_span": "mystery drug", "drug_code": "FAKE_DRUG", "qty": 10,
             "confidence": 0.3},
        ]
        items = validate_extraction(raw_items, self.CANDIDATES, "2026-10-01")
        assert "invalid_drug_code" in items[0].flags
        assert items[0].drug_code is None

    def test_unknown_drug_code_passes(self):
        raw_items = [
            {"raw_span": "mystery drug", "drug_code": "UNKNOWN", "qty": 10,
             "confidence": 0.3},
        ]
        items = validate_extraction(raw_items, self.CANDIDATES, "2026-10-01")
        assert "invalid_drug_code" not in items[0].flags
        assert items[0].drug_code is None

    def test_strip_unit_converts(self):
        raw_items = [
            {"raw_span": "pcm 5 strips", "drug_code": "PCM", "qty": 5,
             "unit": "strip", "confidence": 0.9},
        ]
        items = validate_extraction(raw_items, self.CANDIDATES, "2026-10-01")
        assert items[0].unit == "tablet"
        assert items[0].qty == 50

    def test_unknown_unit_flagged(self):
        raw_items = [
            {"raw_span": "pcm", "drug_code": "PCM", "qty": 10,
             "unit": "barrel", "confidence": 0.9},
        ]
        items = validate_extraction(raw_items, self.CANDIDATES, "2026-10-01")
        assert "unknown_unit" in items[0].flags
        assert items[0].unit is None

    def test_empty_batch_becomes_none(self):
        raw_items = [
            {"raw_span": "insulin", "drug_code": "INSULIN", "qty": 10,
             "batch_no": "", "confidence": 0.8},
        ]
        items = validate_extraction(raw_items, self.CANDIDATES, "2026-10-01")
        assert items[0].batch_no is None

    def test_confidence_clamped(self):
        raw_items = [
            {"raw_span": "insulin", "drug_code": "INSULIN", "qty": 10,
             "confidence": 1.5},
        ]
        items = validate_extraction(raw_items, self.CANDIDATES, "2026-10-01")
        assert items[0].confidence == 1.0


# ---------------------------------------------------------------------------
# Date resolution
# ---------------------------------------------------------------------------

class TestDateResolution:
    def test_dd_mm_future(self):
        result = _resolve_date("15/11", date(2026, 10, 1))
        assert result == "2026-11-15"

    def test_dd_mm_past_wraps_year(self):
        result = _resolve_date("15/03", date(2026, 10, 1))
        assert result == "2027-03-15"

    def test_mm_yyyy(self):
        result = _resolve_date("03/2027", None)
        assert result == "2027-03-01"

    def test_iso_passthrough(self):
        result = _resolve_date("2027-06-30", None)
        assert result == "2027-06-30"

    def test_invalid_returns_none(self):
        result = _resolve_date("not-a-date", None)
        assert result is None

    def test_none_returns_none(self):
        result = _resolve_date(None, None)
        assert result is None


# ---------------------------------------------------------------------------
# Unit normalization
# ---------------------------------------------------------------------------

class TestUnitNormalization:
    def test_strip_to_tablet(self):
        unit, mult = _normalize_unit("strip")
        assert unit == "tablet"
        assert mult == 10

    def test_vial_passthrough(self):
        unit, mult = _normalize_unit("vial")
        assert unit == "vial"
        assert mult == 1

    def test_unknown_unit(self):
        unit, mult = _normalize_unit("barrel")
        assert unit is None
        assert mult == 1

    def test_none_unit(self):
        unit, mult = _normalize_unit(None)
        assert unit is None
        assert mult == 1


# ---------------------------------------------------------------------------
# Full pipeline with mocked genai
# ---------------------------------------------------------------------------

class TestFullPipeline:
    MOCK_GENAI_RESPONSE = {
        "ok": True,
        "output": {
            "items": [
                {
                    "raw_span": "ಇನ್ಸುಲಿನ್ 40IU - 20 vials",
                    "drug_code": "INSULIN",
                    "batch_no": "INS-001",
                    "expiry": "2027-03-15",
                    "qty": 20,
                    "unit": "vial",
                    "confidence": 0.95,
                },
                {
                    "raw_span": "ಪ್ಯಾರಸಿಟಮಾಲ್ 500 - 100 tabs",
                    "drug_code": "PCM",
                    "qty": 100,
                    "unit": "tablet",
                    "confidence": 0.9,
                },
            ]
        },
        "model": "gemini-3.8-flash",
        "cached": False,
        "fallback": False,
    }

    @pytest.mark.asyncio
    async def test_full_pipeline_kannada(self):
        text = "ಇನ್ಸುಲಿನ್ 40IU - 20 vials, batch INS-001, exp 2027-03-15. ಪ್ಯಾರಸಿಟಮಾಲ್ 500 - 100 tabs"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = self.MOCK_GENAI_RESPONSE

        with patch("app.extraction.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            items = await extract_from_text(
                text, "2026-10-01", "H3", genai_url="http://fake:8003",
            )

        assert len(items) == 2
        codes = {it.drug_code for it in items}
        assert "INSULIN" in codes
        assert "PCM" in codes

        insulin = [it for it in items if it.drug_code == "INSULIN"][0]
        assert insulin.qty == 20
        assert insulin.batch_no == "INS-001"
        assert insulin.expiry == "2027-03-15"

    @pytest.mark.asyncio
    async def test_pipeline_genai_failure_returns_empty(self):
        text = "ಇನ್ಸುಲಿನ್ 40IU - 20 vials"

        with patch("app.extraction.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            items = await extract_from_text(
                text, "2026-10-01", "H3", genai_url="http://fake:8003",
            )

        assert items == []

    @pytest.mark.asyncio
    async def test_candidates_constrain_llm(self):
        """Verify the candidates sent to genai only contain grounded drug codes."""
        text = "ಇನ್ಸುಲಿನ್ 40IU - 20 vials, ಪ್ಯಾರಸಿಟಮಾಲ್ 100 tabs"
        captured_payload = {}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "ok": True,
            "output": {"items": []},
        }

        async def capture_post(url, json=None, **kwargs):
            captured_payload.update(json or {})
            return mock_resp

        with patch("app.extraction.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = capture_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await extract_from_text(
                text, "2026-10-01", "H3", genai_url="http://fake:8003",
            )

        candidates = captured_payload.get("input", {}).get("candidates", [])
        for c in candidates:
            assert c["drug_code"] in {"INSULIN", "PCM", "ORS", "AMOX", "OXYTOCIN",
                                       "ASV", "TD", "CEFTRIAXONE", "RL", "METFORMIN",
                                       "AMLODIPINE", "IFA", "MORPHINE"}, (
                f"Unknown code {c['drug_code']} in candidates"
            )

    @pytest.mark.asyncio
    async def test_no_candidates_skips_llm(self):
        text = "hello this is just a greeting"

        with patch("app.extraction.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            items = await extract_from_text(
                text, "2026-10-01", "H3", genai_url="http://fake:8003",
            )

        assert items == []
        mock_client.post.assert_not_called()


import httpx
