"""Tests for forecast service: baseline, context guardrails, runner, backtest."""
from __future__ import annotations

import math
import os
from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from app.baseline import holt_winters_forecast, ewma_forecast
from app.context import (
    apply_guardrails, relevant_signals, get_context_multiplier,
    ContextResult, MULTIPLIER_MIN, MULTIPLIER_MAX, CONFIDENCE_THRESHOLD,
    SEASONAL_CALENDAR,
)
from app.store import ForecastStore, ForecastRow
from app.runner import run_forecast


# ── Baseline tests ───────────────────────────────────────────────────────────

class TestHoltWinters:
    def test_on_seasonal_data(self):
        """Holt-Winters should detect weekly seasonality."""
        import math
        series = []
        for i in range(90):
            seasonal = 10 + 3 * math.sin(2 * math.pi * i / 7)
            noise = 0.5 * (i % 3 - 1)
            series.append(max(0, seasonal + noise))

        result = holt_winters_forecast(series, 30)
        assert result.method == "holt_winters"
        assert result.daily_rate > 0
        assert result.p10 >= 0
        assert result.p90 > result.p10

    def test_short_series_falls_back_to_ewma(self):
        series = [5.0, 6.0, 4.0, 7.0, 5.5]
        result = holt_winters_forecast(series, 30)
        assert result.method == "ewma"
        assert result.daily_rate > 0

    def test_empty_series(self):
        result = holt_winters_forecast([], 30)
        assert result.method == "ewma"
        assert result.daily_rate == 0.0

    def test_constant_series(self):
        series = [10.0] * 30
        result = holt_winters_forecast(series, 30)
        assert abs(result.daily_rate - 10.0) < 3.0

    def test_residuals_populated(self):
        import math
        series = [10 + 2 * math.sin(2 * math.pi * i / 7) for i in range(90)]
        result = holt_winters_forecast(series, 30)
        assert len(result.residuals) == len(series)


class TestEWMA:
    def test_basic(self):
        series = [10.0, 12.0, 11.0, 13.0, 10.0]
        result = ewma_forecast(series)
        assert result.method == "ewma"
        assert result.daily_rate > 0

    def test_empty(self):
        result = ewma_forecast([])
        assert result.daily_rate == 0.0

    def test_single_value(self):
        result = ewma_forecast([7.0])
        assert abs(result.daily_rate - 7.0) < 0.01


# ── Context guardrail tests ─────────────────────────────────────────────────

class TestGuardrails:
    def test_clamp_high(self):
        signals = [{"id": "s1", "type": "outbreak", "params": {}}]
        result = apply_guardrails(
            {"multiplier": 5.0, "confidence": 0.9, "signal_ids": ["s1"], "reasoning": "test"},
            signals,
        )
        assert result.multiplier == MULTIPLIER_MAX

    def test_clamp_low(self):
        signals = [{"id": "s1", "type": "outbreak", "params": {}}]
        result = apply_guardrails(
            {"multiplier": 0.1, "confidence": 0.8, "signal_ids": ["s1"], "reasoning": "test"},
            signals,
        )
        assert result.multiplier == MULTIPLIER_MIN

    def test_no_valid_citation_returns_1(self):
        signals = [{"id": "s1", "type": "outbreak", "params": {}}]
        result = apply_guardrails(
            {"multiplier": 2.0, "confidence": 0.9, "signal_ids": ["FAKE_ID"], "reasoning": "test"},
            signals,
        )
        assert result.multiplier == 1.0
        assert result.method == "guardrail_fallback"

    def test_empty_citation_returns_1(self):
        signals = [{"id": "s1", "type": "outbreak", "params": {}}]
        result = apply_guardrails(
            {"multiplier": 2.0, "confidence": 0.9, "signal_ids": [], "reasoning": "test"},
            signals,
        )
        assert result.multiplier == 1.0

    def test_low_confidence_returns_1(self):
        signals = [{"id": "s1", "type": "outbreak", "params": {}}]
        result = apply_guardrails(
            {"multiplier": 2.0, "confidence": 0.3, "signal_ids": ["s1"], "reasoning": "test"},
            signals,
        )
        assert result.multiplier == 1.0
        assert "low confidence" in result.reasoning

    def test_valid_passes_through(self):
        signals = [{"id": "s1", "type": "outbreak", "params": {}}]
        result = apply_guardrails(
            {"multiplier": 1.8, "confidence": 0.85, "signal_ids": ["s1"], "reasoning": "dengue spike"},
            signals,
        )
        assert result.multiplier == 1.8
        assert result.method == "llm"
        assert "s1" in result.signal_ids

    def test_at_confidence_threshold(self):
        signals = [{"id": "s1", "type": "x", "params": {}}]
        result = apply_guardrails(
            {"multiplier": 1.5, "confidence": 0.5, "signal_ids": ["s1"], "reasoning": "ok"},
            signals,
        )
        assert result.multiplier == 1.5  # exactly at threshold passes


# ── Signal relevance tests ───────────────────────────────────────────────────

class TestRelevantSignals:
    def test_matching_facility_drug(self):
        signals = [
            {"id": "s1", "type": "outbreak", "params": {"facility_id": "H3", "drug_code": "ORS"}},
            {"id": "s2", "type": "outbreak", "params": {"facility_id": "H1", "drug_code": "PCM"}},
        ]
        rel = relevant_signals("H3", "ORS", signals)
        assert len(rel) == 1
        assert rel[0]["id"] == "s1"

    def test_no_match(self):
        signals = [
            {"id": "s1", "type": "outbreak", "params": {"facility_id": "H3", "drug_code": "ORS"}},
        ]
        rel = relevant_signals("H1", "PCM", signals)
        assert len(rel) == 0

    def test_seasonal_affects_filter(self):
        seasonal = [
            {"id": "season_winter", "type": "winter", "months": [11],
             "params": {"affects": ["PCM", "AMOX500"]}, "fired_at": "seasonal"},
        ]
        rel = relevant_signals("H1", "PCM", seasonal)
        assert len(rel) == 1

        rel2 = relevant_signals("H1", "ORS", seasonal)
        assert len(rel2) == 0

    def test_no_facility_filter_matches_all(self):
        signals = [
            {"id": "s1", "type": "campaign", "params": {"drug_code": "ORS"}},
        ]
        rel = relevant_signals("H1", "ORS", signals)
        assert len(rel) == 1


# ── No-signal path: zero LLM calls ──────────────────────────────────────────

class TestNoSignalPath:
    def test_no_signals_means_zero_llm_calls(self):
        """When no signals exist, no LLM calls should be made."""
        with patch("app.runner.fetch_signals", return_value=[]):
            result = run_forecast(
                date(2026, 11, 1),
                facility_filter="H1",
                drug_filter="PARA500",
            )
            assert result["llm_calls"] == 0
            assert result["forecasts"] >= 1


# ── Store tests ──────────────────────────────────────────────────────────────

class TestStore:
    def test_upsert_and_get(self):
        store = ForecastStore()
        row = ForecastRow("H1", "D1", 30, 10.0, "ewma", 0.9, 1.0, 10.0)
        store.upsert(row)
        got = store.get("H1", "D1")
        assert got is not None
        assert got.daily_rate == 10.0

    def test_list_filter(self):
        store = ForecastStore()
        store.upsert(ForecastRow("H1", "D1", 30, 10.0, "ewma", 0.9, 1.0, 10.0))
        store.upsert(ForecastRow("H2", "D1", 30, 8.0, "ewma", 0.8, 1.0, 8.0))
        store.upsert(ForecastRow("H1", "D2", 30, 5.0, "ewma", 0.7, 1.0, 5.0))

        assert len(store.list_all()) == 3
        assert len(store.list_all(facility="H1")) == 2
        assert len(store.list_all(drug="D1")) == 2


# ── Runner integration ───────────────────────────────────────────────────────

class TestRunner:
    def test_run_produces_forecasts(self):
        from app.store import forecast_store
        forecast_store.clear()

        with patch("app.runner.fetch_signals", return_value=[]):
            result = run_forecast(date(2026, 11, 1))

        assert result["forecasts"] > 0
        rows = forecast_store.list_all()
        assert len(rows) > 0
        for r in rows:
            assert r.daily_rate >= 0
            assert r.adjusted_rate >= 0
            assert r.context_multiplier == 1.0  # no signals → 1.0


# ── API integration ──────────────────────────────────────────────────────────

class TestAPI:
    def test_forecast_run(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        with patch("app.runner.fetch_signals", return_value=[]):
            resp = client.post("/forecast/run", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "forecasts" in data
        assert data["forecasts"] > 0

    def test_get_forecasts(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        # First run
        with patch("app.runner.fetch_signals", return_value=[]):
            client.post("/forecast/run", json={})

        resp = client.get("/forecast")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "daily_rate" in data[0]
        assert "context_multiplier" in data[0]

    def test_get_forecasts_filtered(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        with patch("app.runner.fetch_signals", return_value=[]):
            client.post("/forecast/run", json={})

        resp = client.get("/forecast?facility=H1")
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["facility_id"] == "H1" for r in data)

    def test_backtest_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        with patch("app.runner.fetch_signals", return_value=[]):
            client.post("/forecast/run", json={})

        resp = client.get("/forecast/backtest")
        assert resp.status_code == 200
        data = resp.json()
        assert "mae" in data
        assert "rmse" in data
        assert "coverage" in data
        assert "periods" in data

    def test_health(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
