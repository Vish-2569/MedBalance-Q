"""Holt-Winters baseline forecasting with EWMA fallback.

Pure functions — no I/O except what callers pass in.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class BaselineResult:
    daily_rate: float
    method: str  # "holt_winters" or "ewma"
    p10: float
    p90: float
    residuals: list[float]


MIN_HW_DAYS = 14  # need at least 2 full weeks for weekly seasonality


def holt_winters_forecast(
    series: list[float],
    horizon_days: int = 30,
) -> BaselineResult:
    """Fit Holt-Winters with weekly seasonality; fallback to EWMA if too short."""
    if len(series) < MIN_HW_DAYS:
        return ewma_forecast(series, horizon_days)

    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        arr = np.array(series, dtype=float)
        arr = np.maximum(arr, 0)

        seasonal_periods = 7
        if len(arr) < 2 * seasonal_periods:
            return ewma_forecast(series, horizon_days)

        model = ExponentialSmoothing(
            arr,
            seasonal_periods=seasonal_periods,
            trend="add",
            seasonal="add",
            initialization_method="estimated",
        )
        fit = model.fit(optimized=True, use_brute=False)

        forecast_vals = fit.forecast(horizon_days)
        daily_rate = float(np.mean(np.maximum(forecast_vals, 0)))

        fitted = fit.fittedvalues
        residuals = (arr - fitted).tolist()

        abs_residuals = np.abs(residuals)
        p10 = max(0, daily_rate - float(np.percentile(abs_residuals, 90)))
        p90 = daily_rate + float(np.percentile(abs_residuals, 90))

        return BaselineResult(
            daily_rate=round(daily_rate, 2),
            method="holt_winters",
            p10=round(p10, 2),
            p90=round(p90, 2),
            residuals=[round(r, 3) for r in residuals],
        )

    except Exception:
        return ewma_forecast(series, horizon_days)


def ewma_forecast(
    series: list[float],
    horizon_days: int = 30,
    alpha: float = 0.3,
) -> BaselineResult:
    """Exponentially weighted moving average fallback."""
    if not series:
        return BaselineResult(
            daily_rate=0.0, method="ewma", p10=0.0, p90=0.0, residuals=[],
        )

    ewma = series[0]
    residuals: list[float] = []

    for val in series:
        residuals.append(val - ewma)
        ewma = alpha * val + (1 - alpha) * ewma

    daily_rate = max(0.0, ewma)

    abs_res = [abs(r) for r in residuals]
    if abs_res:
        sorted_res = sorted(abs_res)
        idx_90 = min(int(len(sorted_res) * 0.9), len(sorted_res) - 1)
        spread = sorted_res[idx_90]
    else:
        spread = 0.0

    p10 = max(0, daily_rate - spread)
    p90 = daily_rate + spread

    return BaselineResult(
        daily_rate=round(daily_rate, 2),
        method="ewma",
        p10=round(p10, 2),
        p90=round(p90, 2),
        residuals=[round(r, 3) for r in residuals],
    )
