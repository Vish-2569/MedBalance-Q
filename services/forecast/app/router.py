"""Forecast API routes."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from medbal_common.clock import today as clock_today
from medbal_common.logging import get_logger

from .backtest import run_backtest
from .runner import run_forecast, _load_fixture_data
from .store import forecast_store

log = get_logger("forecast.router")

router = APIRouter()


class ForecastRunRequest(BaseModel):
    facility_id: str | None = None
    drug_code: str | None = None


@router.post("/forecast/run")
async def forecast_run(req: ForecastRunRequest):
    today = clock_today()
    result = run_forecast(
        today,
        facility_filter=req.facility_id,
        drug_filter=req.drug_code,
    )
    return result


@router.get("/forecast")
async def get_forecasts(
    facility: str | None = Query(None),
    drug: str | None = Query(None),
):
    rows = forecast_store.list_all(facility=facility, drug=drug)
    return [r.to_dict() for r in rows]


@router.get("/forecast/backtest")
async def backtest():
    _, _, consumption = _load_fixture_data()
    result = run_backtest(consumption)
    return result
