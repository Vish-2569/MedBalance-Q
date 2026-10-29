"""Lot endpoints: list and upsert-batch."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from medbal_common.db import session_scope
from medbal_common import audit, bus

from ..queries import list_lots, upsert_lot

router = APIRouter()


class LotIn(BaseModel):
    facility_id: str
    drug_code: str
    batch_no: str
    expiry: str
    qty: int


@router.get("/lots")
async def get_lots(facility: str | None = None, drug: str | None = None):
    with session_scope() as s:
        return JSONResponse(list_lots(s, facility, drug))


@router.post("/lots/upsert-batch")
async def upsert_batch(items: list[LotIn]):
    affected: dict[str, set[str]] = {}
    count = 0
    with session_scope() as s:
        for item in items:
            old_qty, new_qty = upsert_lot(s, item.model_dump())
            audit.append(
                s,
                actor="system",
                action="lot.upsert",
                entity="lot",
                entity_id=f"{item.facility_id}:{item.drug_code}:{item.batch_no}",
                payload={"old_qty": old_qty, "new_qty": new_qty},
            )
            affected.setdefault(item.facility_id, set()).add(item.drug_code)
            count += 1

    for fac_id, drugs in affected.items():
        bus.publish("inventory.updated", {
            "facility_id": fac_id,
            "drug_codes": sorted(drugs),
            "reason": "ingest",
        })

    return JSONResponse({"upserted": count})
