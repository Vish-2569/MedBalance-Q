"""H4-style messy free-text register report with typos and inconsistencies."""
from __future__ import annotations

import hashlib

from ..hospital_config import DRUG_INFO

HEADERS = [
    "Stock register – {facility} – {date}",
    "Daily stock count {date} {facility}",
    "{facility} medicine register {date}",
    "stock report {facility} dt {date}",
    "STOCK POSITION {date}",
    "medicine stock {facility} {date}",
    "daily register {date} - {facility}",
    "Stock Report as on {date}",
    "{facility} stock register dated {date}",
    "Stck regstr {facility} {date}",
    "drug stock report {date}",
]

DATE_FORMATS = [
    lambda d: f"{d[8:10]}-{_month_abbr(d[5:7])}-{d[0:4]}",  # 03-Nov-2026
    lambda d: f"{_month_abbr(d[5:7]).lower()} {d[2:4]}",      # nov 26
    lambda d: f"{d[5:7]}/{d[0:4]}",                            # 11/2026
    lambda d: f"{d[8:10]}/{d[5:7]}/{d[0:4]}",                  # 03/11/2026
    lambda d: f"{d[8:10]}.{d[5:7]}.{d[2:4]}",                  # 03.11.26
]

_MONTHS = {
    "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
    "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
}


def _month_abbr(mm: str) -> str:
    return _MONTHS.get(mm, mm)


def _row_hash(drug_code: str, seed: int, day_index: int) -> int:
    key = f"messy:{drug_code}:{seed}:{day_index}"
    return int.from_bytes(hashlib.md5(key.encode()).digest()[:4], "little")


def generate(
    facility_id: str,
    date_str: str,
    lots: list[dict],
    seed: int,
    day_index: int,
    bad_data: bool = False,
) -> str:
    rng_base = seed + day_index * 13

    header_tmpl = HEADERS[rng_base % len(HEADERS)]
    header = header_tmpl.format(facility=facility_id, date=date_str)
    lines = [header, "=" * min(len(header), 40), ""]

    drug_lots: dict[str, list[dict]] = {}
    for lot in lots:
        if lot.get("qty", 0) <= 0 and lot.get("status") == "expired":
            continue
        dc = lot["drug_code"]
        drug_lots.setdefault(dc, []).append(lot)

    for dc in sorted(drug_lots.keys()):
        info = DRUG_INFO.get(dc, {})
        rh = _row_hash(dc, seed, day_index)

        # Use typo name ~50% of the time, real name otherwise
        if rh % 2 == 0:
            drug_name = info.get("typo", dc.lower())
        else:
            drug_name = info.get("name", dc).lower()

        unit = info.get("unit", "unit")
        # Sometimes omit unit
        if rh % 7 == 0:
            unit = ""

        for lot in drug_lots[dc]:
            qty = lot["qty"]
            batch = lot["batch_no"]
            expiry = lot["expiry"]

            # Cycle through date formats
            fmt_idx = (rh + day_index) % len(DATE_FORMATS)
            exp_str = DATE_FORMATS[fmt_idx](expiry)

            # ~25% omit batch
            if rh % 4 == 0:
                batch_part = ""
            else:
                batch_part = f" batch {batch}"

            unit_part = f" {unit}" if unit else ""
            lines.append(f"{drug_name} - {qty}{unit_part}{batch_part} exp {exp_str}")

    # bad_data injection: absurd quantity and impossible expiry
    if bad_data:
        lines.append("")
        lines.append("inzulin - 10000 vial batch BAD-001 exp 12/1999")
        lines.append("paracetmol - 10000 tablet exp jan 1999")

    lines.append("")
    lines.append("---end---")
    return "\n".join(lines)
