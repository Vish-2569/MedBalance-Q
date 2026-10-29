"""Deterministic anomaly detection rules for ingested stock items."""
from __future__ import annotations

from datetime import date, timedelta

from .adapters import ExtractionItem

MAX_FUTURE_YEARS = 5
QTY_SPIKE_FACTOR = 10
LOW_CONFIDENCE_THRESHOLD = 0.85


def check_anomalies(
    item: ExtractionItem,
    facility_code: str,
    today: date,
    *,
    typical_qty: int | None = None,
    lots_by_batch: dict[str, list[dict]] | None = None,
) -> list[str]:
    """Run all anomaly rules. Returns list of triggered rule codes."""
    rules: list[str] = []

    if _check_qty_spike(item, typical_qty):
        rules.append("qty_spike")
    if _check_past_expiry(item, today):
        rules.append("past_expiry")
    if _check_far_future_expiry(item, today):
        rules.append("far_future_expiry")
    if _check_batch_mismatch(item, facility_code, lots_by_batch):
        rules.append("batch_mismatch")
    if _check_unknown_drug(item):
        rules.append("unknown_drug")
    if _check_low_confidence(item):
        rules.append("low_confidence")

    return rules


def _check_qty_spike(item: ExtractionItem, typical_qty: int | None) -> bool:
    if typical_qty is None or typical_qty <= 0:
        return False
    if item.qty is None:
        return False
    return item.qty > QTY_SPIKE_FACTOR * typical_qty


def _check_past_expiry(item: ExtractionItem, today: date) -> bool:
    if not item.expiry:
        return False
    try:
        exp = date.fromisoformat(item.expiry)
        return exp < today
    except (ValueError, TypeError):
        return False


def _check_far_future_expiry(item: ExtractionItem, today: date) -> bool:
    if not item.expiry:
        return False
    try:
        exp = date.fromisoformat(item.expiry)
        return exp > today + timedelta(days=MAX_FUTURE_YEARS * 365)
    except (ValueError, TypeError):
        return False


def _check_batch_mismatch(
    item: ExtractionItem,
    facility_code: str,
    lots_by_batch: dict[str, list[dict]] | None,
) -> bool:
    if not lots_by_batch or not item.batch_no or not item.expiry:
        return False
    existing = lots_by_batch.get(item.batch_no, [])
    for lot in existing:
        if lot.get("facility_id") != facility_code and lot.get("expiry") != item.expiry:
            return True
    return False


def _check_unknown_drug(item: ExtractionItem) -> bool:
    return item.drug_code is None


def _check_low_confidence(item: ExtractionItem) -> bool:
    return item.confidence < LOW_CONFIDENCE_THRESHOLD


RULE_TEMPLATES: dict[str, str] = {
    "qty_spike": "Quantity {qty} is unusually high for this facility's typical stock of ~{typical} units.",
    "past_expiry": "Expiry date {expiry} is in the past (today is {today}).",
    "far_future_expiry": "Expiry date {expiry} is more than 5 years in the future.",
    "batch_mismatch": "Batch {batch_no} exists at another facility with a different expiry date.",
    "unknown_drug": "Drug could not be identified from the report text '{drug_name}'.",
    "low_confidence": "Extraction confidence ({confidence:.0%}) is below the 85% threshold.",
}


def build_fallback_explanation(
    item: ExtractionItem,
    rules: list[str],
    today: date,
    typical_qty: int | None = None,
) -> str:
    """Build a deterministic explanation from templates when LLM is unavailable."""
    parts: list[str] = []
    for rule in rules:
        template = RULE_TEMPLATES.get(rule, f"Anomaly rule '{rule}' triggered.")
        try:
            parts.append(template.format(
                qty=item.qty,
                typical=typical_qty or "unknown",
                expiry=item.expiry,
                today=today.isoformat(),
                batch_no=item.batch_no,
                drug_name=item.drug_name_raw,
                confidence=item.confidence,
            ))
        except (KeyError, ValueError):
            parts.append(f"Anomaly rule '{rule}' triggered.")
    return " ".join(parts)
