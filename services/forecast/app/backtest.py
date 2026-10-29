"""Backtest: MAPE for baseline vs adjusted forecasts over the scenario window."""
from __future__ import annotations

import math
from typing import Any

from .store import forecast_store


def run_backtest(
    actual_consumption: dict[tuple[str, str], list[float]],
) -> dict[str, Any]:
    """Compare forecast accuracy: baseline rate vs adjusted rate against actuals.

    actual_consumption: {(facility_id, drug_code): [daily values for the test window]}
    """
    baseline_errors: list[float] = []
    adjusted_errors: list[float] = []
    per_pair: list[dict[str, Any]] = []
    periods = 0

    for row in forecast_store.list_all():
        key = (row.facility_id, row.drug_code)
        actuals = actual_consumption.get(key, [])
        if not actuals:
            continue

        actual_rate = sum(actuals) / len(actuals) if actuals else 0
        periods += len(actuals)

        if actual_rate > 0:
            base_mape = abs(row.daily_rate - actual_rate) / actual_rate
            adj_mape = abs(row.adjusted_rate - actual_rate) / actual_rate
        else:
            base_mape = 0.0 if row.daily_rate == 0 else 1.0
            adj_mape = 0.0 if row.adjusted_rate == 0 else 1.0

        baseline_errors.append(base_mape)
        adjusted_errors.append(adj_mape)

        per_pair.append({
            "facility_id": row.facility_id,
            "drug_code": row.drug_code,
            "actual_rate": round(actual_rate, 2),
            "baseline_rate": row.daily_rate,
            "adjusted_rate": row.adjusted_rate,
            "multiplier": row.context_multiplier,
            "baseline_mape": round(base_mape, 4),
            "adjusted_mape": round(adj_mape, 4),
        })

    avg_base_mape = _mean(baseline_errors)
    avg_adj_mape = _mean(adjusted_errors)

    base_rmse = math.sqrt(_mean([e**2 for e in baseline_errors])) if baseline_errors else 0
    adj_rmse = math.sqrt(_mean([e**2 for e in adjusted_errors])) if adjusted_errors else 0

    return {
        "baseline_mape": round(avg_base_mape, 4),
        "adjusted_mape": round(avg_adj_mape, 4),
        "baseline_rmse": round(base_rmse, 4),
        "adjusted_rmse": round(adj_rmse, 4),
        "pairs_evaluated": len(per_pair),
        "periods": periods,
        "per_pair": per_pair,
        "mae": round(avg_adj_mape, 4),
        "rmse": round(adj_rmse, 4),
        "coverage": round(len(per_pair) / max(len(forecast_store.list_all()), 1), 2),
    }


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0
