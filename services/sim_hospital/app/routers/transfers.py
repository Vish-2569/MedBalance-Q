"""Transfer endpoints: inbound and outbound stock movements."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from .. import stock_db

router = APIRouter()


class TransferItem(BaseModel):
    drug_code: str
    drug_name: str = ""
    batch_no: str
    qty: int
    usable: int = 0
    expiry: str | None = None
    status: str = "active"


class TransferRequest(BaseModel):
    order_id: str
    items: list[TransferItem]


@router.post("/transfers/outbound")
async def dispatch_outbound(req: TransferRequest):
    dispatched = 0
    for item in req.items:
        lots = stock_db.get_active_lots(item.drug_code)
        for lot in lots:
            if lot["batch_no"] == item.batch_no and lot["qty"] >= item.qty:
                stock_db.decrement_lot(item.drug_code, item.batch_no, item.qty)
                dispatched += 1
                break
    return {"dispatched": dispatched}


@router.post("/transfers/inbound")
async def receive_inbound(req: TransferRequest):
    accepted = 0
    for item in req.items:
        expiry = item.expiry or "2099-12-31"
        stock_db.upsert_lot(item.drug_code, item.batch_no, expiry, item.qty, status=item.status)
        accepted += 1
    return {"accepted": accepted}
