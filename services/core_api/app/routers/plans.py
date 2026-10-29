"""POST /plans — persist a plan run with orders and regret."""
from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from medbal_common.db import session_scope
from medbal_common.clock import now
from medbal_common.settings import settings
from medbal_common import audit, bus

from ..queries import (
    insert_plan_run,
    insert_candidate,
    insert_transfer_order,
    insert_regret,
    get_next_dta_seq,
)

router = APIRouter()


def _make_dta_number(seq: int, year: int) -> str:
    return f"DTA/BLR-U/{year}/{seq:06d}"


def _make_qr_token(order_id: str) -> str:
    secret = settings.QR_HMAC_SECRET or "dev-secret"
    return hmac.new(secret.encode(), order_id.encode(), hashlib.sha256).hexdigest()


class _PlanPayload:
    def __init__(self, data: dict):
        self.plan = data["plan"]
        self.candidates = data.get("candidates", [])
        self.orders = data.get("orders", [])
        self.regret = data.get("regret", [])


@router.post("/plans", status_code=201)
async def persist_plan(payload: dict):
    p = _PlanPayload(payload)
    plan_id = p.plan["id"]
    ts = now()
    year = ts.year

    with session_scope() as s:
        insert_plan_run(s, p.plan)
        audit.append(s, "optimizer", "plan.created", "plan_run", plan_id,
                     {"solver_tier": p.plan["solver_tier"], "transfers": p.plan.get("transfers", 0)})

        for c in p.candidates:
            insert_candidate(s, plan_id, c)

        dta_seq = get_next_dta_seq(s)
        for order in p.orders:
            if not order.get("dta_number"):
                order["dta_number"] = _make_dta_number(dta_seq, year)
                dta_seq += 1
            order["plan_id"] = plan_id
            order.setdefault("qr_token", _make_qr_token(order["id"]))
            insert_transfer_order(s, order)
            audit.append(s, "optimizer", "order.created", "order", order["id"],
                         {"dta_number": order["dta_number"], "qty": order["qty"],
                          "drug_code": order["drug_code"]})

        for r in p.regret:
            insert_regret(s, plan_id, r)

    bus.publish("plan.completed", {
        "plan_id": plan_id,
        "transfers": p.plan.get("transfers", len(p.orders)),
        "shortage_reduction": p.plan.get("shortage_reduction"),
        "solver_tier": p.plan["solver_tier"],
        "energy": p.plan.get("energy"),
    })

    return JSONResponse({"plan_id": plan_id}, status_code=201)
