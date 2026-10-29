"""H2-style e-Aushadhi CSV report with realistic quirks."""
from __future__ import annotations

import hashlib
import io
import csv

from ..hospital_config import DRUG_INFO


def _row_hash(facility_id: str, batch_no: str, seed: int, day_index: int) -> int:
    key = f"{facility_id}:{batch_no}:{seed}:{day_index}"
    return int.from_bytes(hashlib.md5(key.encode()).digest()[:4], "little")


def generate(
    facility_id: str,
    date_str: str,
    lots: list[dict],
    seed: int,
    day_index: int,
) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Facility Code", "Drug Name", "Batch No", "Exp Date", "Qty", "Unit"])

    for lot in lots:
        if lot.get("qty", 0) <= 0 and lot.get("status") == "expired":
            continue

        dc = lot["drug_code"]
        info = DRUG_INFO.get(dc, {})
        drug_name = info.get("csv_name", dc)
        unit = info.get("unit", "unit")
        qty = lot["qty"]
        batch = lot["batch_no"]
        expiry = lot["expiry"]

        rh = _row_hash(facility_id, batch, seed, day_index)

        # ~20% of rows: missing batch number
        if rh % 5 == 0:
            batch = ""

        # Tablets and capsules: ~20% reported in strips (÷10)
        if unit in ("tablet", "capsule") and rh % 5 == 1:
            qty = max(1, qty // 10)
            unit = "strip"

        # Format expiry as MM/YYYY
        try:
            parts = expiry.split("-")
            exp_formatted = f"{parts[1]}/{parts[0]}"
        except (IndexError, ValueError):
            exp_formatted = expiry

        writer.writerow([facility_id, drug_name, batch, exp_formatted, qty, unit])

    return buf.getvalue()
