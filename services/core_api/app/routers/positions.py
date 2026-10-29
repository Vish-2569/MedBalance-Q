"""Positions read-model using FEFO math."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from medbal_common.db import session_scope
from medbal_common.clock import today
from medbal_common.fefo import compute_position

from ..queries import (
    facility_drug_groups,
    get_lots_for_position,
    get_consumption_rate,
    get_policy,
)

router = APIRouter()


def _compute_all_positions(session, t, facility: str | None = None, drug: str | None = None) -> list[dict]:
    groups = facility_drug_groups(session)
    if facility:
        groups = [(f, d) for f, d in groups if f == facility]
    if drug:
        groups = [(f, d) for f, d in groups if d == drug]

    results = []
    for fac_id, drug_code in groups:
        lots = get_lots_for_position(session, fac_id, drug_code)
        rate = get_consumption_rate(session, fac_id, drug_code, t)
        policy = get_policy(session, fac_id, drug_code)

        pos = compute_position(
            facility_id=fac_id,
            drug_code=drug_code,
            lots=lots,
            rate=rate,
            today=t,
            min_reserve_days=policy["min_reserve_days"],
            target_days=policy["target_days"],
            lead_time_days=policy["lead_time_days"],
        )
        results.append({
            "facility_id": pos.facility_id,
            "drug_code": pos.drug_code,
            "effective_stock": pos.effective_stock,
            "at_risk": pos.at_risk,
            "reserve": pos.reserve,
            "shortage": pos.shortage,
            "consumption_rate": pos.rate,
            "target_days": pos.target_days,
        })
    return results


@router.get("/positions")
async def get_positions(facility: str | None = None, drug: str | None = None):
    t = today()
    with session_scope() as s:
        return JSONResponse(_compute_all_positions(s, t, facility, drug))
