"""Numeric grounding firewall for LLM narrations.

Extracts all numbers, dates, percentages, and currency amounts from the
narration text, normalises them, and checks each against the fact set.
Any miss → grounding_ok=false, replaced with deterministic template.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from medbal_common.logging import get_logger

log = get_logger("genai.firewall")

# Regex for Indian number formats: 1,50,000 or 1500 or 1,500.50
# Plain numbers use negative lookbehind to skip digits in identifiers (H1, H3)
_NUM_RE = re.compile(
    r"₹\s*([\d,]+(?:\.\d+)?)"       # ₹ prefixed amounts
    r"|(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"  # dates like 15/11/2026 or 2026-11-15
    r"|(\d{4}-\d{2}-\d{2})"         # ISO dates
    r"|(\d[\d,]*(?:\.\d+)?)\s*%"    # percentages
    r"|(?<![A-Za-z\-\d])(\d[\d,]*(?:\.\d+)?)(?!\w)"  # plain numbers, not part of identifiers
)


def _parse_indian_number(s: str) -> float:
    """Parse a number that may use Indian comma grouping (1,50,000)."""
    cleaned = s.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return float("nan")


def _parse_date_str(s: str) -> str | None:
    """Try to parse a date string into ISO format."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%Y", "%d/%m/%y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date().isoformat()
        except ValueError:
            continue
    return None


def extract_values(text: str) -> list[dict[str, Any]]:
    """Extract all numeric/date values from narration text."""
    values: list[dict[str, Any]] = []

    for match in _NUM_RE.finditer(text):
        rupee, date_slash, date_iso, pct, plain = match.groups()

        if rupee:
            values.append({
                "type": "currency",
                "raw": match.group(0),
                "value": _parse_indian_number(rupee),
            })
        elif date_slash:
            parsed = _parse_date_str(date_slash)
            if parsed:
                values.append({"type": "date", "raw": date_slash, "value": parsed})
        elif date_iso:
            values.append({"type": "date", "raw": date_iso, "value": date_iso})
        elif pct:
            values.append({
                "type": "percentage",
                "raw": match.group(0),
                "value": _parse_indian_number(pct),
            })
        elif plain:
            val = _parse_indian_number(plain)
            if val == val:  # not NaN
                values.append({"type": "number", "raw": plain, "value": val})

    return values


def _build_fact_set(facts: dict[str, Any]) -> dict[str, set[Any]]:
    """Build a lookup of all acceptable values from the order facts."""
    numbers: set[float] = set()
    dates: set[str] = set()
    percentages: set[float] = set()
    currencies: set[float] = set()

    for key, val in facts.items():
        if val is None:
            continue
        if isinstance(val, (int, float)):
            numbers.add(float(val))
            currencies.add(float(val))
        elif isinstance(val, str):
            # Try as date
            parsed = _parse_date_str(val)
            if parsed:
                dates.add(parsed)
            # Try as number
            try:
                numbers.add(float(val.replace(",", "")))
            except (ValueError, AttributeError):
                pass
        elif isinstance(val, date):
            dates.add(val.isoformat())
        elif isinstance(val, dict):
            for v in val.values():
                if isinstance(v, (int, float)):
                    numbers.add(float(v))
                elif isinstance(v, str):
                    p = _parse_date_str(v)
                    if p:
                        dates.add(p)

    return {"numbers": numbers, "dates": dates, "percentages": percentages, "currencies": currencies}


def _check_value(
    extracted: dict[str, Any],
    fact_set: dict[str, set[Any]],
    tolerance: float = 0.005,
) -> bool:
    """Check if an extracted value matches any fact. Percentages allow ±0.5%."""
    vtype = extracted["type"]
    val = extracted["value"]

    if vtype == "date":
        return val in fact_set["dates"]

    if vtype == "percentage":
        for fv in fact_set["numbers"] | fact_set["percentages"]:
            if fv == 0:
                if val == 0:
                    return True
            elif abs(val - fv) / max(abs(fv), 1e-9) <= tolerance:
                return True
        return False

    # number or currency: exact match in the fact set
    all_nums = fact_set["numbers"] | fact_set["currencies"]
    if val in all_nums:
        return True
    # tolerance for derived values
    for fv in all_nums:
        if fv == 0:
            if val == 0:
                return True
        elif abs(val - fv) / max(abs(fv), 1e-9) <= tolerance:
            return True
    return False


def check_narration(
    narration: str,
    facts: dict[str, Any],
) -> dict[str, Any]:
    """Run the firewall on a narration. Returns grounding result.

    Returns:
        {
            "grounding_ok": bool,
            "narration": str (original or deterministic replacement),
            "extracted_values": [...],
            "mismatches": [...],
        }
    """
    extracted = extract_values(narration)
    fact_set = _build_fact_set(facts)

    mismatches: list[dict[str, Any]] = []
    for ev in extracted:
        if not _check_value(ev, fact_set):
            mismatches.append(ev)

    if mismatches:
        log.warning(
            "firewall_block",
            mismatches=len(mismatches),
            values=[m["raw"] for m in mismatches],
        )
        replacement = _deterministic_narration(facts)
        return {
            "grounding_ok": False,
            "narration": replacement,
            "extracted_values": extracted,
            "mismatches": mismatches,
            "original_narration": narration,
        }

    return {
        "grounding_ok": True,
        "narration": narration,
        "extracted_values": extracted,
        "mismatches": [],
    }


def _deterministic_narration(facts: dict[str, Any]) -> str:
    """Generate a deterministic template narration from facts."""
    drug = facts.get("drug_name", facts.get("drug_code", "medicine"))
    qty = facts.get("qty", "?")
    unit = facts.get("unit", "units")
    src = facts.get("src_facility", facts.get("src_facility_id", "source"))
    dst = facts.get("dst_facility", facts.get("dst_facility_id", "destination"))
    usable = facts.get("usable", qty)
    expiry = facts.get("expiry", "")
    shortage_before = facts.get("shortage_before", "?")
    shortage_after = facts.get("shortage_after", "?")

    parts = [
        f"Transfer {qty} {unit} of {drug} from {src} to {dst}.",
        f"{usable} {unit} usable at destination before expiry {expiry}.",
    ]
    if shortage_before and shortage_after:
        parts.append(
            f"Reduces {dst} shortage from {shortage_before} to {shortage_after} {unit}."
        )
    return " ".join(parts)
