"""GET /provenance/{order_id} — full provenance bundle."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from medbal_common.db import session_scope

from ..queries import get_provenance

router = APIRouter()


@router.get("/provenance/{order_id}")
async def provenance(order_id: str):
    with session_scope() as s:
        result = get_provenance(s, order_id)
    if not result:
        raise HTTPException(404, f"Order {order_id} not found")
    return JSONResponse(result)
