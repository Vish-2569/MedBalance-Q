"""Pull-mode report endpoints for H1 (FHIR) and H2 (CSV)."""
from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from .. import stock_db
from ..reporters import fhir, csv_report

router = APIRouter()

_seed = int(os.environ.get("SIM_SEED", "42"))
_day_index_counter: int = 0


def set_day_index(idx: int) -> None:
    global _day_index_counter
    _day_index_counter = idx


@router.get("/fhir/InventoryReport")
async def fhir_inventory_report():
    lots = stock_db.get_all_lots()
    facility_id = stock_db.get_facility_id()
    try:
        from medbal_common.clock import today
        date_str = str(today())
    except Exception:
        date_str = "2026-11-01"
    return fhir.generate(facility_id, date_str, lots)


@router.get("/export/stock.csv")
async def csv_stock_export():
    lots = stock_db.get_all_lots()
    facility_id = stock_db.get_facility_id()
    try:
        from medbal_common.clock import today
        date_str = str(today())
    except Exception:
        date_str = "2026-11-01"
    content = csv_report.generate(facility_id, date_str, lots, _seed, _day_index_counter)
    return PlainTextResponse(content, media_type="text/csv")
