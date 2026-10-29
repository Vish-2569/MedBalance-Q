"""Custody endpoints: chain query, QR scan with HMAC verification and state machine."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from medbal_common.db import session_scope
from medbal_common.clock import now
from medbal_common.settings import settings
from medbal_common import audit, bus
from medbal_common.logging import get_logger

from ..queries import (
    get_custody_events,
    get_order_with_token,
    update_order_status,
    insert_custody_event,
    get_last_custody_event,
    list_routes,
)

log = get_logger("core.custody")

router = APIRouter()

VALID_TRANSITIONS = {
    "dispatch": ("approved",),
    "receive": ("dispatched",),
    "consume": ("received",),
}

SIM_HOSPITAL_URLS = {
    "H1": "http://sim-hospital-h1:8101",
    "H2": "http://sim-hospital-h2:8102",
    "H3": "http://sim-hospital-h3:8103",
    "H4": "http://sim-hospital-h4:8104",
}

COLDCHAIN_URL = "http://coldchain:8006"


def _verify_token(token: str, order_id: str) -> bool:
    secret = settings.QR_HMAC_SECRET or "dev-secret"
    expected = hmac.new(secret.encode(), order_id.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(token, expected)


def _find_order_by_token(token: str) -> str | None:
    """Brute-search isn't needed: token = HMAC(secret, order_id), so we look up by qr_token."""
    with session_scope() as s:
        from sqlalchemy import text
        row = s.execute(
            text("SELECT id FROM transfer_order WHERE qr_token = :token"),
            {"token": token},
        ).fetchone()
        return row.id if row else None


async def _check_excursion(vehicle_id: str | None, dispatched_at: str | None) -> bool:
    if not vehicle_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{COLDCHAIN_URL}/status")
            if resp.status_code == 200:
                devices = resp.json()
                for d in devices if isinstance(devices, list) else []:
                    if d.get("vehicle_id") == vehicle_id and d.get("alert"):
                        return True
    except Exception:
        pass
    return False


async def _call_sim_hospital(url: str, payload: dict) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                return resp.json()
            log.warning("sim_hospital_error", url=url, status=resp.status_code)
    except Exception as exc:
        log.warning("sim_hospital_unreachable", url=url, error=str(exc))
    return None


async def _request_genai_summary(deviation: dict) -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "http://genai:8003/llm/complete",
                json={
                    "purpose": "deviation_summary",
                    "prompt_id": "deviation_summary",
                    "version": 1,
                    "input": {"deviation": deviation},
                },
            )
            if resp.status_code == 200:
                result = resp.json()
                return result.get("output", {}).get("text", "")
    except Exception:
        pass
    return ""


class ScanRequest(BaseModel):
    token: str
    event: str
    qty: int | None = None
    actor: str = "scanner"


@router.get("/custody/{order_id}")
async def custody_chain(order_id: str):
    with session_scope() as s:
        events = get_custody_events(s, order_id)
    return JSONResponse(events)


@router.post("/custody/scan")
async def scan_custody(req: ScanRequest):
    if req.event not in VALID_TRANSITIONS:
        raise HTTPException(400, f"Invalid event '{req.event}'. Must be one of: dispatch, receive, consume")

    order_id = _find_order_by_token(req.token)
    if not order_id:
        if not _verify_token(req.token, ""):
            raise HTTPException(403, "Invalid HMAC token")
        raise HTTPException(404, "Order not found for token")

    if not _verify_token(req.token, order_id):
        raise HTTPException(403, "Invalid HMAC token")

    ts = now()

    with session_scope() as s:
        order = get_order_with_token(s, order_id)
        if not order:
            raise HTTPException(404, f"Order {order_id} not found")

        current_status = order["status"]
        required = VALID_TRANSITIONS[req.event]
        if current_status not in required:
            raise HTTPException(
                409,
                f"Cannot {req.event}: order status is '{current_status}', "
                f"must be one of {required}",
            )

        scan_qty = req.qty if req.qty is not None else order["qty"]
        deviations = []

        if req.event == "dispatch":
            new_status = "dispatched"
            update_order_status(s, order_id, new_status, dispatched_at=ts.isoformat())

        elif req.event == "receive":
            new_status = "received"

            dispatched_qty = order["qty"]
            if scan_qty != dispatched_qty:
                deviations.append({
                    "type": "qty_mismatch",
                    "expected": dispatched_qty,
                    "actual": scan_qty,
                    "delta": scan_qty - dispatched_qty,
                })

            if order.get("dispatched_at"):
                dispatch_dt = order["dispatched_at"]
                if isinstance(dispatch_dt, str):
                    try:
                        dispatch_dt = datetime.fromisoformat(dispatch_dt)
                    except ValueError:
                        dispatch_dt = None
                if dispatch_dt:
                    routes = list_routes(s)
                    route = next(
                        (r for r in routes
                         if r["src_facility_id"] == order["src_facility_id"]
                         and r["dst_facility_id"] == order["dst_facility_id"]),
                        None,
                    )
                    if route:
                        eta = dispatch_dt + timedelta(hours=route["transit_hours"])
                        deadline = eta + timedelta(days=1)
                        if ts > deadline:
                            deviations.append({
                                "type": "late_arrival",
                                "eta": eta.isoformat(),
                                "arrived_at": ts.isoformat(),
                                "delay_hours": round((ts - eta).total_seconds() / 3600, 1),
                            })

            excursion = await _check_excursion(order.get("vehicle_id"), order.get("dispatched_at"))
            if excursion and order["temperature_req"] == "cold_chain":
                deviations.append({"type": "cold_chain_excursion", "vehicle_id": order.get("vehicle_id")})

            update_order_status(s, order_id, new_status, received_at=ts.isoformat())

        elif req.event == "consume":
            new_status = "consumed"
            update_order_status(s, order_id, new_status)

        deviation_json = json.dumps(deviations) if deviations else None

        event_record = {
            "order_id": order_id,
            "event_type": req.event,
            "actor": req.actor,
            "qty": scan_qty,
            "timestamp": ts.isoformat(),
            "location": order.get("dst_facility_id") if req.event in ("receive", "consume") else order.get("src_facility_id"),
            "temperature_c": None,
            "deviation": deviation_json,
            "notes": f"{len(deviations)} deviation(s) detected" if deviations else None,
        }
        event_id = insert_custody_event(s, event_record)

        audit.append(
            s, req.actor, f"custody.{req.event}", "order", order_id,
            {"event": req.event, "qty": scan_qty, "status": new_status,
             "deviations": len(deviations)},
        )

    if req.event == "dispatch":
        src_url = SIM_HOSPITAL_URLS.get(order["src_facility_id"])
        if src_url:
            await _call_sim_hospital(f"{src_url}/transfers/outbound", {
                "order_id": order_id,
                "items": [{
                    "drug_code": order["drug_code"],
                    "drug_name": order["drug_name"],
                    "batch_no": order["batch_no"],
                    "qty": scan_qty,
                    "usable": order["usable"],
                    "expiry": None,
                }],
            })

    elif req.event == "receive":
        dst_url = SIM_HOSPITAL_URLS.get(order["dst_facility_id"])
        if dst_url:
            lot_status = "quarantined" if any(d["type"] == "cold_chain_excursion" for d in deviations) else "active"
            await _call_sim_hospital(f"{dst_url}/transfers/inbound", {
                "order_id": order_id,
                "items": [{
                    "drug_code": order["drug_code"],
                    "drug_name": order["drug_name"],
                    "batch_no": order["batch_no"],
                    "qty": scan_qty,
                    "usable": order["usable"],
                    "expiry": None,
                    "status": lot_status,
                }],
            })

    bus.publish("custody.scanned", {
        "order_id": order_id,
        "event": req.event,
        "qty": scan_qty,
        "actor": req.actor,
        "deviations": deviations,
    })

    if deviations:
        summary = await _request_genai_summary(deviations)
        if not summary:
            summary = "; ".join(d["type"] for d in deviations)

    response = {
        "order_id": order_id,
        "event": req.event,
        "status": new_status,
        "qty": scan_qty,
        "custody_event_id": event_id,
    }
    if deviations:
        response["deviations"] = deviations
        response["deviation_summary"] = summary

    return JSONResponse(response)
