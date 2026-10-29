"""Tests for the four hospital report adapters."""
from __future__ import annotations

import pytest

from app.adapters import FhirAdapter, CsvAdapter, ChatAdapter, TextAdapter

from conftest import SAMPLE_FHIR, SAMPLE_CSV


class TestFhirAdapter:
    def test_parses_items(self):
        adapter = FhirAdapter()
        report = adapter.parse("H1", SAMPLE_FHIR)
        assert report.format == "fhir"
        assert report.facility_code == "H1"
        assert len(report.items) == 2

    def test_extracts_drug_code(self):
        adapter = FhirAdapter()
        report = adapter.parse("H1", SAMPLE_FHIR)
        codes = [it.drug_code for it in report.items]
        assert "INSULIN" in codes
        assert "PCM" in codes

    def test_extracts_qty_and_unit(self):
        adapter = FhirAdapter()
        report = adapter.parse("H1", SAMPLE_FHIR)
        insulin = [it for it in report.items if it.drug_code == "INSULIN"][0]
        assert insulin.qty == 50
        assert insulin.unit == "vial"

    def test_extracts_batch_and_expiry(self):
        adapter = FhirAdapter()
        report = adapter.parse("H1", SAMPLE_FHIR)
        insulin = [it for it in report.items if it.drug_code == "INSULIN"][0]
        assert insulin.batch_no == "INS-2026-001"
        assert insulin.expiry == "2027-03-15"

    def test_confidence_is_one(self):
        adapter = FhirAdapter()
        report = adapter.parse("H1", SAMPLE_FHIR)
        for it in report.items:
            assert it.confidence == 1.0

    def test_reported_datetime(self):
        adapter = FhirAdapter()
        report = adapter.parse("H1", SAMPLE_FHIR)
        assert report.reported_at == "2026-11-01T10:00:00"

    def test_empty_listing(self):
        empty = {
            "resourceType": "InventoryReport",
            "reportedDateTime": "2026-11-01T10:00:00",
            "inventoryListing": [],
        }
        report = FhirAdapter().parse("H1", empty)
        assert report.items == []


class TestCsvAdapter:
    def test_parses_rows(self):
        adapter = CsvAdapter()
        report = adapter.parse("H2", SAMPLE_CSV)
        assert report.format == "csv"
        assert len(report.items) == 3

    def test_expiry_mm_yyyy_to_iso(self):
        adapter = CsvAdapter()
        report = adapter.parse("H2", SAMPLE_CSV)
        pcm = report.items[0]
        assert pcm.expiry == "2027-06-01"

    def test_empty_batch_is_none(self):
        adapter = CsvAdapter()
        report = adapter.parse("H2", SAMPLE_CSV)
        amox = report.items[1]
        assert amox.batch_no is None

    def test_strip_unit_flagged(self):
        adapter = CsvAdapter()
        report = adapter.parse("H2", SAMPLE_CSV)
        strip_items = [it for it in report.items if it.unit == "strip"]
        assert len(strip_items) == 1
        assert "unit_conversion_needed" in strip_items[0].flags

    def test_confidence_is_09(self):
        adapter = CsvAdapter()
        report = adapter.parse("H2", SAMPLE_CSV)
        for it in report.items:
            assert it.confidence == 0.9

    def test_raw_text_stored(self):
        adapter = CsvAdapter()
        report = adapter.parse("H2", SAMPLE_CSV)
        assert report.raw_text == SAMPLE_CSV


class TestChatAdapter:
    def test_stores_raw_text(self):
        msg = "ಇನ್ಸುಲಿನ್ 40IU - 20 vials, batch INS-001, exp 2027-03"
        report = ChatAdapter().parse("H3", msg)
        assert report.format == "chat"
        assert report.raw_text == msg
        assert report.items == []

    def test_facility_code(self):
        report = ChatAdapter().parse("H3", "test")
        assert report.facility_code == "H3"


class TestTextAdapter:
    def test_stores_raw_text(self):
        msg = "Insulin 50 vials batch INS-2026-001 exp Mar 2027"
        report = TextAdapter().parse("H4", msg)
        assert report.format == "text"
        assert report.raw_text == msg
        assert report.items == []

    def test_facility_code(self):
        report = TextAdapter().parse("H4", "test")
        assert report.facility_code == "H4"
