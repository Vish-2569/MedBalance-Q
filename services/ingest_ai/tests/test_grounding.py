"""Tests for drug name grounding module."""
from __future__ import annotations

import pytest

from app.grounding import ground_drug, reload_index


@pytest.fixture(autouse=True)
def fresh_index():
    reload_index()
    yield
    reload_index()


class TestExactMatch:
    def test_exact_code(self):
        r = ground_drug("INSULIN")
        assert r.drug_code == "INSULIN"
        assert r.score == 100
        assert r.method == "exact"

    def test_exact_name_case_insensitive(self):
        r = ground_drug("paracetamol 500mg")
        assert r.drug_code == "PCM"
        assert r.score == 100

    def test_exact_alias(self):
        r = ground_drug("amoxicillin")
        assert r.drug_code == "AMOX"
        assert r.score == 100
        assert r.method == "exact"

    def test_exact_kannada_alias(self):
        r = ground_drug("ಇನ್ಸುಲಿನ್")
        assert r.drug_code == "INSULIN"
        assert r.score == 100


class TestFuzzyMatch:
    def test_misspelling_inzulin(self):
        r = ground_drug("inzulin")
        assert r.drug_code == "INSULIN"
        assert r.score > 85
        assert r.method in ("exact", "fuzzy")

    def test_kannada_paracetamol(self):
        r = ground_drug("ಪ್ಯಾರಸಿಟಮಾಲ್")
        assert r.drug_code == "PCM"
        assert r.score > 80

    def test_csv_drug_name(self):
        r = ground_drug("Amoxycillin 500mg Cap")
        assert r.drug_code == "AMOX"
        assert r.score >= 70

    def test_typo_oxytosin(self):
        r = ground_drug("oxytosin")
        assert r.drug_code == "OXYTOCIN"
        assert r.score >= 70

    def test_abbreviation_pcm(self):
        r = ground_drug("pcm")
        assert r.drug_code == "PCM"


class TestUnknown:
    def test_garbage_returns_unknown(self):
        r = ground_drug("xyzzy_not_a_drug_12345")
        assert r.drug_code is None
        assert r.method == "unknown"

    def test_empty_string(self):
        r = ground_drug("")
        assert r.drug_code is None
        assert r.method == "unknown"

    def test_whitespace_only(self):
        r = ground_drug("   ")
        assert r.drug_code is None
