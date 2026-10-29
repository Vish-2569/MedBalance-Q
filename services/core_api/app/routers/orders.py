"""Order endpoints: list, get, approve, reject."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from medbal_common.db import session_scope
from medbal_common.clock import now
from medbal_common.logging import get_logger
from medbal_common import audit, bus

from ..queries import list_orders, get_order, approve_order, reject_order

log = get_logger("core.orders")

router = APIRouter()

GENAI_URL = "http://genai:8003"


class RejectBody(BaseModel):
    reason: str
    actor: str = "district_officer"


class ApproveBody(BaseModel):
    actor: str = "district_officer"


@router.get("/orders")
async def get_orders(plan_id: str | None = None, status: str | None = None):
    with session_scope() as s:
        return JSONResponse(list_orders(s, plan_id, status))


@router.get("/orders/{order_id}")
async def get_order_by_id(order_id: str):
    with session_scope() as s:
        order = get_order(s, order_id)
    if not order:
        raise HTTPException(404, f"Order {order_id} not found")
    return JSONResponse(order)


@router.post("/orders/{order_id}/approve")
async def approve(order_id: str, body: ApproveBody | None = None):
    actor = body.actor if body else "district_officer"
    ts = now()
    with session_scope() as s:
        existing = get_order(s, order_id)
        if not existing:
            raise HTTPException(404, f"Order {order_id} not found")
        if existing["status"] != "proposed":
            raise HTTPException(409, f"Order status is {existing['status']}, cannot approve")

        order = approve_order(s, order_id, actor, ts)
        audit.append(s, actor, "order.approved", "order", order_id,
                     {"old_status": "proposed", "new_status": "approved"})

    bus.publish("order.status", {
        "order_id": order_id,
        "plan_id": order["plan_id"],
        "old_status": "proposed",
        "new_status": "approved",
        "actor": actor,
    })

    _trigger_dta_generation(order)

    return JSONResponse(order)


@router.post("/orders/{order_id}/reject")
async def reject(order_id: str, body: RejectBody):
    ts = now()
    with session_scope() as s:
        existing = get_order(s, order_id)
        if not existing:
            raise HTTPException(404, f"Order {order_id} not found")
        if existing["status"] != "proposed":
            raise HTTPException(409, f"Order status is {existing['status']}, cannot reject")

        order = reject_order(s, order_id, body.reason, ts)
        audit.append(s, body.actor, "order.rejected", "order", order_id,
                     {"old_status": "proposed", "new_status": "rejected",
                      "reason": body.reason})

    bus.publish("order.status", {
        "order_id": order_id,
        "plan_id": order["plan_id"],
        "old_status": "proposed",
        "new_status": "rejected",
        "actor": body.actor,
    })
    return JSONResponse(order)


def _trigger_dta_generation(order: dict) -> None:
    """Fire-and-forget DTA voucher generation via genai service."""
    try:
        with httpx.Client(timeout=2.0) as client:
            client.post(
                f"{GENAI_URL}/narrate/{order['id']}",
                json={"order_facts": order},
            )
    except Exception as exc:
        log.warning("dta_trigger_failed", order_id=order["id"], error=str(exc))
