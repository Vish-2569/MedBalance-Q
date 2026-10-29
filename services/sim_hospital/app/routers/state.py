"""State, reset, and health endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from .. import stock_db

router = APIRouter()


@router.get("/state")
async def get_state():
    facility_id = stock_db.get_facility_id()
    lots = stock_db.get_all_lots()
    base_rates = stock_db.get_base_rates()

    drugs: dict[str, dict] = {}
    for lot in lots:
        dc = lot["drug_code"]
        if dc not in drugs:
            drugs[dc] = {
                "drug_code": dc,
                "lots": [],
                "consumption_rate": base_rates.get(dc, 0.0),
            }
        drugs[dc]["lots"].append(
            {
                "facility_id": facility_id,
                "drug_code": dc,
                "batch_no": lot["batch_no"],
                "expiry": lot["expiry"],
                "qty": lot["qty"],
            }
        )

    try:
        from medbal_common.clock import today

        sim_date = today().isoformat()
    except Exception:
        sim_date = None

    return {
        "hospital_id": facility_id,
        "sim_date": sim_date,
        "drugs": list(drugs.values()),
    }


@router.post("/reset")
async def reset():
    hospital_id = stock_db.get_hospital_id()
    stock_db.reset(hospital_id)
    return {"status": "reset", "hospital_id": stock_db.get_facility_id()}
