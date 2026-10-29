"""Custody endpoints: chain query and scan (scan is 501 until P17)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from medbal_common.db import session_scope

from ..queries import get_custody_events

router = APIRouter()


@router.get("/custody/{order_id}")
async def custody_chain(order_id: str):
    with session_scope() as s:
        events = get_custody_events(s, order_id)
    return JSONResponse(events)


@router.post("/custody/scan", status_code=501)
async def scan_custody():
    raise HTTPException(501, "Custody scanning not implemented yet (P17)")
