"""Forecast runner: orchestrates baseline + context multiplier for all pairs."""
from __future__ import annotations

import time
from datetime import date, datetime, timezone
from typing import Any

import httpx

from medbal_common.logging import get_logger
from medbal_common.settings import settings
from medbal_common import bus

from .baseline import holt_winters_forecast
from .context import fetch_signals, get_context_multiplier, relevant_signals
from .store import ForecastRow, forecast_store

log = get_logger("forecast.runner")

CORE_API_URL = "http://core-api:8001"
HORIZON_DAYS = 30


def run_forecast(
    today: date,
    *,
    facility_filter: str | None = None,
    drug_filter: str | None = None,
) -> dict[str, Any]:
    """Run forecast for all (or filtered) facility×drug pairs."""
    t0 = time.perf_counter()

    facilities, drugs, consumption = _load_data(facility_filter, drug_filter)
    signals = fetch_signals(today)

    count = 0
    llm_calls = 0

    for fac in facilities:
        fac_id = fac["id"]
        fac_name = fac.get("name", fac_id)

        for drug in drugs:
            drug_code = drug["code"]

            if facility_filter and fac_id != facility_filter:
                continue
            if drug_filter and drug_code != drug_filter:
                continue

            series = consumption.get((fac_id, drug_code), [])

            # Baseline
            bl = holt_winters_forecast(series, HORIZON_DAYS)

            # Context multiplier
            rel = relevant_signals(fac_id, drug_code, signals)
            if rel:
                ctx = get_context_multiplier(
                    facility_id=fac_id,
                    facility_name=fac_name,
                    drug_code=drug_code,
                    drug_name=drug.get("name", drug_code),
                    unit=drug.get("unit", "unit"),
                    baseline_rate=bl.daily_rate,
                    recent_14d=series[-14:] if series else [],
                    signals=signals,
                )
                llm_calls += 1 if ctx.method == "llm" else 0
            else:
                from .context import ContextResult
                ctx = ContextResult(
                    multiplier=1.0, confidence=1.0, signal_ids=[],
                    reasoning="No relevant signals", method="no_signal",
                )

            adjusted = round(bl.daily_rate * ctx.multiplier, 2)

            row = ForecastRow(
                facility_id=fac_id,
                drug_code=drug_code,
                horizon_days=HORIZON_DAYS,
                daily_rate=bl.daily_rate,
                method=f"{bl.method}{'_llm' if ctx.method == 'llm' else ''}",
                confidence=ctx.confidence,
                context_multiplier=ctx.multiplier,
                adjusted_rate=adjusted,
                p10=round(bl.p10 * ctx.multiplier, 2),
                p90=round(bl.p90 * ctx.multiplier, 2),
                signal_ids=ctx.signal_ids,
                reasoning=ctx.reasoning,
                computed_at=datetime.now(timezone.utc).isoformat(),
            )
            forecast_store.upsert(row)
            count += 1

    _publish_updated(count)

    ms = (time.perf_counter() - t0) * 1000
    return {
        "forecasts": count,
        "method": "holt_winters+context",
        "llm_calls": llm_calls,
        "time_ms": round(ms, 1),
    }


def _load_data(
    facility_filter: str | None,
    drug_filter: str | None,
) -> tuple[list[dict], list[dict], dict[tuple[str, str], list[float]]]:
    """Load facilities, drugs, consumption history from core-api or fixtures."""
    if settings.USE_FIXTURES:
        return _load_fixture_data()

    facilities = []
    drugs = []
    consumption: dict[tuple[str, str], list[float]] = {}

    try:
        resp = httpx.get(f"{CORE_API_URL}/facilities", timeout=5.0)
        resp.raise_for_status()
        facilities = resp.json()
    except Exception as e:
        log.warning("facilities_fetch_failed", error=str(e))

    try:
        resp = httpx.get(f"{CORE_API_URL}/drugs", timeout=5.0)
        resp.raise_for_status()
        drugs = resp.json()
    except Exception as e:
        log.warning("drugs_fetch_failed", error=str(e))

    # Consumption history from core-api or sim-hospitals
    for fac in facilities:
        fac_id = fac["id"]
        if fac_id == "W0":
            continue
        if facility_filter and fac_id != facility_filter:
            continue
        try:
            resp = httpx.get(
                f"{CORE_API_URL}/consumption",
                params={"facility_id": fac_id},
                timeout=5.0,
            )
            if resp.status_code == 200:
                for rec in resp.json():
                    key = (rec["facility_id"], rec["drug_code"])
                    consumption.setdefault(key, []).append(rec.get("qty", 0))
        except Exception:
            pass

    return facilities, drugs, consumption


def _load_fixture_data():
    """Generate synthetic consumption for fixture facilities+drugs."""
    import json
    import math
    import random
    from pathlib import Path

    fixtures_dir = Path(__file__).resolve().parents[2] / ".." / "contracts" / "fixtures"
    fixtures_dir = fixtures_dir.resolve()

    snapshot = json.loads((fixtures_dir / "snapshot.json").read_text())
    facilities = [f for f in snapshot["facilities"] if f["id"] != "W0"]
    drugs = snapshot["drugs"]

    rng = random.Random(42)
    consumption: dict[tuple[str, str], list[float]] = {}

    for fac in facilities:
        fac_id = fac["id"]
        for drug in drugs:
            dc = drug["code"]
            base_rate = rng.uniform(2, 15)
            series = []
            for day in range(90):
                seasonal = 1 + 0.2 * math.sin(2 * math.pi * day / 7)
                noise = rng.gauss(0, base_rate * 0.15)
                val = max(0, base_rate * seasonal + noise)
                series.append(round(val, 1))
            consumption[(fac_id, dc)] = series

    return facilities, drugs, consumption


def _publish_updated(count: int) -> None:
    try:
        bus.publish("forecast.updated", {"count": count})
    except Exception:
        pass
