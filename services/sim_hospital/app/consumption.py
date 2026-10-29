"""Poisson demand generation and FEFO dispensing logic."""
from __future__ import annotations

import hashlib
import json

import numpy as np

from medbal_common.settings import settings

from . import stock_db


def stable_drug_hash(drug_code: str) -> int:
    """Deterministic hash — Python hash() is randomized across processes."""
    return int.from_bytes(
        hashlib.md5(drug_code.encode()).digest()[:4], "little"
    ) % 100_000


def compute_demand(
    drug_code: str,
    base_rate: float,
    multiplier: float,
    day_index: int,
    seed: int,
) -> int:
    lam = base_rate * multiplier
    if lam <= 0:
        return 0
    drug_hash = stable_drug_hash(drug_code)
    rng = np.random.default_rng(seed + day_index * 1000 + drug_hash)
    return int(rng.poisson(lam))


def dispense_fefo(drug_code: str, demand: int) -> tuple[int, int]:
    """Dispense FEFO from active lots. Returns (dispensed, stockout_qty)."""
    if demand <= 0:
        return 0, 0

    lots = stock_db.get_active_lots(drug_code)
    dispensed = 0
    remaining = demand

    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot["qty"], remaining)
        if take > 0:
            stock_db.decrement_lot(drug_code, lot["batch_no"], take)
            dispensed += take
            remaining -= take

    stockout_qty = max(0, demand - dispensed)
    return dispensed, stockout_qty


def get_multiplier_for(facility: str, drug_code: str, day_index: int) -> float:
    """Read demand multiplier from Redis (set by sim-control scenarios)."""
    try:
        from medbal_common.bus import get_redis

        r = get_redis()
        raw = r.get("sim:demand_multipliers")
        if raw:
            for m in json.loads(raw):
                if (
                    m["facility"] == facility
                    and m["drug_code"] == drug_code
                    and m["start_day"] <= day_index <= m["end_day"]
                ):
                    return float(m["multiplier"])
    except Exception:
        pass
    return 1.0


def process_tick(date_str: str, day_index: int) -> None:
    """Process one sim day: expire, demand, dispense FEFO, log."""
    facility = stock_db.get_facility_id()
    base_rates = stock_db.get_base_rates()
    seed = settings.SIM_SEED

    stock_db.expire_lots(date_str)

    for drug_code, base_rate in base_rates.items():
        multiplier = get_multiplier_for(facility, drug_code, day_index)
        demand = compute_demand(drug_code, base_rate, multiplier, day_index, seed)
        dispensed, stockout_qty = dispense_fefo(drug_code, demand)
        stock_db.insert_consumption(date_str, drug_code, demand, dispensed, stockout_qty)
