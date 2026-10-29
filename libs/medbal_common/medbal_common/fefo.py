from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date


@dataclass
class LotPosition:
    batch_no: str
    expiry: date
    qty: int
    effective: int
    at_risk: int
    reserved: int
    transferable: int


@dataclass
class PositionResult:
    facility_id: str
    drug_code: str
    effective_stock: int
    at_risk: int
    reserve: int
    shortage: int
    rate: float
    target_days: int
    lots: list[LotPosition] = field(default_factory=list)


def compute_position(
    facility_id: str,
    drug_code: str,
    lots: list[dict],
    rate: float,
    today: date,
    min_reserve_days: int = 7,
    target_days: int = 21,
    lead_time_days: int = 3,
) -> PositionResult:
    if not lots:
        shortage = max(0, math.ceil(rate * target_days)) if rate > 0 else 0
        return PositionResult(
            facility_id=facility_id,
            drug_code=drug_code,
            effective_stock=0,
            at_risk=0,
            reserve=0,
            shortage=shortage,
            rate=rate,
            target_days=target_days,
        )

    sorted_lots = sorted(lots, key=lambda l: l["expiry"])

    cumulative_consumed = 0.0
    lot_effectives: list[int] = []
    for lot in sorted_lots:
        days_left = max(0, (lot["expiry"] - today).days)
        capacity = rate * days_left
        consumable = min(lot["qty"], max(0, int(capacity - cumulative_consumed)))
        lot_effectives.append(consumable)
        cumulative_consumed += consumable

    total_qty = sum(l["qty"] for l in sorted_lots)
    effective_stock = sum(lot_effectives)
    total_at_risk = total_qty - effective_stock

    if rate > 0:
        reserve = max(math.ceil(rate * min_reserve_days),
                      math.ceil(rate * lead_time_days * 1.2))
    else:
        reserve = 0

    lot_reserved: list[int] = [0] * len(sorted_lots)
    remaining_reserve = reserve
    for i in reversed(range(len(sorted_lots))):
        if remaining_reserve <= 0:
            break
        take = min(sorted_lots[i]["qty"], remaining_reserve)
        lot_reserved[i] = take
        remaining_reserve -= take

    lot_positions: list[LotPosition] = []
    for i, lot in enumerate(sorted_lots):
        eff = lot_effectives[i]
        lot_positions.append(LotPosition(
            batch_no=lot["batch_no"],
            expiry=lot["expiry"],
            qty=lot["qty"],
            effective=eff,
            at_risk=lot["qty"] - eff,
            reserved=lot_reserved[i],
            transferable=max(0, lot["qty"] - lot_reserved[i]),
        ))

    shortage = max(0, math.ceil(rate * target_days) - effective_stock) if rate > 0 else 0

    return PositionResult(
        facility_id=facility_id,
        drug_code=drug_code,
        effective_stock=effective_stock,
        at_risk=total_at_risk,
        reserve=reserve,
        shortage=shortage,
        rate=rate,
        target_days=target_days,
        lots=lot_positions,
    )
