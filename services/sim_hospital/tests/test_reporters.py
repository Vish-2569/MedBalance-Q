"""Tests for P04b report generators."""
from __future__ import annotations

import csv
import io
import re

from app.reporters import fhir, csv_report, chat_kn, text_messy

SAMPLE_LOTS = [
    {"drug_code": "INSULIN", "batch_no": "B-INS-H1-001", "expiry": "2026-12-15", "qty": 8, "status": "active"},
    {"drug_code": "PCM", "batch_no": "B-PCM-H1-001", "expiry": "2027-03-01", "qty": 200, "status": "active"},
    {"drug_code": "AMOX", "batch_no": "B-AMOX-H1-001", "expiry": "2026-11-20", "qty": 50, "status": "active"},
    {"drug_code": "ORS", "batch_no": "B-ORS-H1-001", "expiry": "2027-06-30", "qty": 100, "status": "active"},
    {"drug_code": "MORPHINE", "batch_no": "B-MOR-H1-001", "expiry": "2027-01-10", "qty": 3, "status": "active"},
]


def test_fhir_structure():
    report = fhir.generate("H1", "2026-11-03", SAMPLE_LOTS)
    assert report["resourceType"] == "InventoryReport"
    assert report["status"] == "current"
    assert report["countType"] == "snapshot"
    assert report["reportedDateTime"] == "2026-11-03"
    assert "inventoryListing" in report
    items = report["inventoryListing"][0]["items"]
    assert len(items) == len(SAMPLE_LOTS)
    codes = {it["code"]["coding"][0]["code"] for it in items}
    assert "INSULIN" in codes
    assert "PCM" in codes


def test_fhir_skips_expired():
    lots = SAMPLE_LOTS + [
        {"drug_code": "RL", "batch_no": "B-RL-001", "expiry": "2026-10-01", "qty": 0, "status": "expired"},
    ]
    report = fhir.generate("H1", "2026-11-03", lots)
    items = report["inventoryListing"][0]["items"]
    codes = {it["code"]["coding"][0]["code"] for it in items}
    assert "RL" not in codes


def test_csv_parseable():
    content = csv_report.generate("H2", "2026-11-03", SAMPLE_LOTS, seed=42, day_index=5)
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    assert rows[0] == ["Facility Code", "Drug Name", "Batch No", "Exp Date", "Qty", "Unit"]
    assert len(rows) >= len(SAMPLE_LOTS) + 1  # header + data rows


def test_csv_has_quirks():
    content = csv_report.generate("H2", "2026-11-03", SAMPLE_LOTS, seed=42, day_index=5)
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)[1:]  # skip header
    has_empty_batch = any(r[2] == "" for r in rows)
    has_strip = any(r[5] == "strip" for r in rows)
    has_mm_yyyy = all(re.match(r"\d{2}/\d{4}", r[3]) for r in rows)
    assert has_mm_yyyy, "All dates should be MM/YYYY"
    # At least one quirk should fire across different seeds
    content2 = csv_report.generate("H2", "2026-11-03", SAMPLE_LOTS, seed=99, day_index=3)
    rows2 = list(csv.reader(io.StringIO(content2)))[1:]
    all_empty_batch = any(r[2] == "" for r in rows + rows2)
    all_strip = any(r[5] == "strip" for r in rows + rows2)
    assert all_empty_batch or all_strip, "CSV quirks should appear across seeds"


def test_chat_kn_kannada():
    text = chat_kn.generate("H3", "2026-11-03", SAMPLE_LOTS, seed=42, day_index=5)
    assert re.search(r"[ಀ-೿]", text), "Should contain Kannada characters"
    assert "exp" in text.lower()


def test_chat_kn_has_drug_entries():
    text = chat_kn.generate("H3", "2026-11-03", SAMPLE_LOTS, seed=42, day_index=5)
    lines = [l for l in text.split("\n") if l.startswith("- ")]
    assert len(lines) >= len(SAMPLE_LOTS)


def test_text_messy_typos():
    text = text_messy.generate("H4", "2026-11-03", SAMPLE_LOTS, seed=42, day_index=5)
    typos = ["inzulin", "paracetmol", "amoxy", "morfine", "ors pkt"]
    has_typo = any(t in text.lower() for t in typos)
    # Also check across a different day_index
    text2 = text_messy.generate("H4", "2026-11-04", SAMPLE_LOTS, seed=42, day_index=6)
    has_typo2 = any(t in text2.lower() for t in typos)
    assert has_typo or has_typo2, "At least one typo should appear"


def test_text_messy_bad_data():
    text = text_messy.generate("H4", "2026-11-03", SAMPLE_LOTS, seed=42, day_index=5, bad_data=True)
    assert "10000" in text
    assert "1999" in text


def test_text_messy_no_bad_data_by_default():
    text = text_messy.generate("H4", "2026-11-03", SAMPLE_LOTS, seed=42, day_index=5, bad_data=False)
    assert "10000" not in text
    assert "1999" not in text


def test_reporter_deterministic():
    lots = SAMPLE_LOTS
    r1 = fhir.generate("H1", "2026-11-03", lots)
    r2 = fhir.generate("H1", "2026-11-03", lots)
    assert r1 == r2

    c1 = csv_report.generate("H2", "2026-11-03", lots, seed=42, day_index=5)
    c2 = csv_report.generate("H2", "2026-11-03", lots, seed=42, day_index=5)
    assert c1 == c2

    k1 = chat_kn.generate("H3", "2026-11-03", lots, seed=42, day_index=5)
    k2 = chat_kn.generate("H3", "2026-11-03", lots, seed=42, day_index=5)
    assert k1 == k2

    t1 = text_messy.generate("H4", "2026-11-03", lots, seed=42, day_index=5)
    t2 = text_messy.generate("H4", "2026-11-03", lots, seed=42, day_index=5)
    assert t1 == t2
