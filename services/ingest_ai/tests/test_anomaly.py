"""Tests for deterministic anomaly detection rules."""
from __future__ import annotations

from datetime import date

from app.adapters import ExtractionItem
from app.anomaly import check_anomalies, build_fallback_explanation


TODAY = date(2026, 10, 29)


def _item(**kwargs) -> ExtractionItem:
    defaults = {
        "drug_name_raw": "Paracetamol",
        "drug_code": "PCM",
        "batch_no": "B001",
        "expiry": "2027-06-01",
        "qty": 100,
        "unit": "tablet",
        "confidence": 0.95,
    }
    defaults.update(kwargs)
    return ExtractionItem(**defaults)


class TestQtySpike:
    def test_fires_when_over_10x(self):
        item = _item(qty=1100)
        rules = check_anomalies(item, "H1", TODAY, typical_qty=100)
        assert "qty_spike" in rules

    def test_skips_when_typical_none(self):
        item = _item(qty=99999)
        rules = check_anomalies(item, "H1", TODAY, typical_qty=None)
        assert "qty_spike" not in rules

    def test_skips_when_below_threshold(self):
        item = _item(qty=500)
        rules = check_anomalies(item, "H1", TODAY, typical_qty=100)
        assert "qty_spike" not in rules

    def test_skips_when_exactly_10x(self):
        item = _item(qty=1000)
        rules = check_anomalies(item, "H1", TODAY, typical_qty=100)
        assert "qty_spike" not in rules


class TestPastExpiry:
    def test_fires_for_past_date(self):
        item = _item(expiry="2025-01-01")
        rules = check_anomalies(item, "H1", TODAY)
        assert "past_expiry" in rules

    def test_skips_for_future_date(self):
        item = _item(expiry="2027-06-01")
        rules = check_anomalies(item, "H1", TODAY)
        assert "past_expiry" not in rules

    def test_skips_when_no_expiry(self):
        item = _item(expiry=None)
        rules = check_anomalies(item, "H1", TODAY)
        assert "past_expiry" not in rules


class TestFarFutureExpiry:
    def test_fires_for_far_future(self):
        item = _item(expiry="2032-01-01")
        rules = check_anomalies(item, "H1", TODAY)
        assert "far_future_expiry" in rules

    def test_skips_within_5_years(self):
        item = _item(expiry="2031-10-01")
        rules = check_anomalies(item, "H1", TODAY)
        assert "far_future_expiry" not in rules


class TestBatchMismatch:
    def test_fires_on_mismatch(self):
        lots = {"B001": [{"facility_id": "H2", "expiry": "2027-12-01"}]}
        item = _item(batch_no="B001", expiry="2027-06-01")
        rules = check_anomalies(item, "H1", TODAY, lots_by_batch=lots)
        assert "batch_mismatch" in rules

    def test_skips_when_same_facility(self):
        lots = {"B001": [{"facility_id": "H1", "expiry": "2027-12-01"}]}
        item = _item(batch_no="B001", expiry="2027-06-01")
        rules = check_anomalies(item, "H1", TODAY, lots_by_batch=lots)
        assert "batch_mismatch" not in rules

    def test_skips_when_no_lots(self):
        item = _item(batch_no="B001")
        rules = check_anomalies(item, "H1", TODAY, lots_by_batch=None)
        assert "batch_mismatch" not in rules


class TestUnknownDrug:
    def test_fires_when_no_code(self):
        item = _item(drug_code=None)
        rules = check_anomalies(item, "H1", TODAY)
        assert "unknown_drug" in rules

    def test_skips_when_code_present(self):
        item = _item(drug_code="PCM")
        rules = check_anomalies(item, "H1", TODAY)
        assert "unknown_drug" not in rules


class TestLowConfidence:
    def test_fires_below_threshold(self):
        item = _item(confidence=0.5)
        rules = check_anomalies(item, "H1", TODAY)
        assert "low_confidence" in rules

    def test_skips_at_threshold(self):
        item = _item(confidence=0.85)
        rules = check_anomalies(item, "H1", TODAY)
        assert "low_confidence" not in rules


class TestCleanItem:
    def test_no_rules_triggered(self):
        item = _item()
        rules = check_anomalies(item, "H1", TODAY)
        assert rules == []


class TestFallbackExplanation:
    def test_generates_text(self):
        item = _item(qty=5000, confidence=0.5)
        rules = ["qty_spike", "low_confidence"]
        explanation = build_fallback_explanation(item, rules, TODAY, typical_qty=100)
        assert "5000" in explanation
        assert "85%" in explanation

    def test_unknown_rule(self):
        item = _item()
        explanation = build_fallback_explanation(item, ["new_rule"], TODAY)
        assert "new_rule" in explanation
