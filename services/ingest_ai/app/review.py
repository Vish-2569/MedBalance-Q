"""In-memory pharmacist review store for flagged extraction items."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field

import httpx

from medbal_common.logging import get_logger

log = get_logger("ingest-ai.review")

CORE_API_URL_DEFAULT = "http://core-api:8001"


@dataclass
class ReviewItem:
    id: str
    report_id: str
    facility_code: str
    item_index: int
    extraction: dict
    anomaly_rules: list[str]
    explanation: str
    raw_excerpt: str | None
    status: str = "needs_review"
    resolved_at: str | None = None
    corrected_values: dict | None = None


_reviews: list[ReviewItem] = []
_aliases: list[dict] = []


def add_review(
    *,
    report_id: str,
    facility_code: str,
    item_index: int,
    extraction: dict,
    anomaly_rules: list[str],
    explanation: str,
    raw_excerpt: str | None = None,
) -> str:
    review_id = str(uuid.uuid4())
    _reviews.append(ReviewItem(
        id=review_id,
        report_id=report_id,
        facility_code=facility_code,
        item_index=item_index,
        extraction=extraction,
        anomaly_rules=anomaly_rules,
        explanation=explanation,
        raw_excerpt=raw_excerpt,
    ))
    return review_id


def list_reviews(
    *,
    facility: str | None = None,
    status: str | None = None,
    drug_code: str | None = None,
) -> list[dict]:
    result = _reviews
    if facility:
        result = [r for r in result if r.facility_code == facility]
    if status:
        result = [r for r in result if r.status == status]
    if drug_code:
        result = [r for r in result if r.extraction.get("drug_code") == drug_code]
    return [_to_dict(r) for r in result]


def get_review(review_id: str) -> ReviewItem | None:
    for r in _reviews:
        if r.id == review_id:
            return r
    return None


async def resolve_review(
    review_id: str,
    action: str,
    corrected_values: dict | None = None,
) -> dict:
    """Resolve a review item: accept, correct, or reject."""
    review = get_review(review_id)
    if review is None:
        return {"error": "not_found"}

    if review.status != "needs_review":
        return {"error": "already_resolved", "status": review.status}

    core_url = os.environ.get("CORE_API_URL", CORE_API_URL_DEFAULT)

    if action == "accept":
        review.status = "accepted"
        review.resolved_at = _now_iso()
        await _upsert_item(review.extraction, review.facility_code, core_url)

    elif action == "correct":
        if not corrected_values:
            return {"error": "corrected_values_required"}
        merged = {**review.extraction, **corrected_values}
        review.status = "corrected"
        review.corrected_values = corrected_values
        review.resolved_at = _now_iso()
        await _upsert_item(merged, review.facility_code, core_url)

        if corrected_values.get("drug_code") and corrected_values["drug_code"] != review.extraction.get("drug_code"):
            alias_entry = {
                "drug_code": corrected_values["drug_code"],
                "alias": review.extraction.get("drug_name_raw", ""),
                "lang": "en",
                "source": "pharmacist_review",
            }
            _aliases.append(alias_entry)
            log.info("alias_captured", **alias_entry)

    elif action == "reject":
        review.status = "rejected"
        review.resolved_at = _now_iso()

    else:
        return {"error": "invalid_action", "valid": ["accept", "correct", "reject"]}

    log.info("review_resolved", review_id=review_id, action=action)
    return _to_dict(review)


def get_aliases() -> list[dict]:
    return list(_aliases)


def clear_store() -> None:
    _reviews.clear()
    _aliases.clear()


async def _upsert_item(extraction: dict, facility_code: str, core_api_url: str) -> None:
    drug_code = extraction.get("drug_code")
    batch_no = extraction.get("batch_no")
    expiry = extraction.get("expiry")
    qty = extraction.get("qty")

    if not all([drug_code, batch_no, expiry, qty]):
        return

    payload = [{
        "facility_id": facility_code,
        "drug_code": drug_code,
        "batch_no": batch_no,
        "expiry": expiry,
        "qty": qty,
    }]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{core_api_url}/lots/upsert-batch", json=payload)
            if resp.status_code != 200:
                log.warning("review_upsert_failed", status=resp.status_code)
    except Exception as exc:
        log.warning("review_upsert_error", error=str(exc))


def _now_iso() -> str:
    try:
        from medbal_common.clock import today
        return today().isoformat()
    except Exception:
        from datetime import date
        return date.today().isoformat()


def _to_dict(r: ReviewItem) -> dict:
    return {
        "id": r.id,
        "report_id": r.report_id,
        "facility_code": r.facility_code,
        "item_index": r.item_index,
        "extraction": r.extraction,
        "anomaly_rules": r.anomaly_rules,
        "explanation": r.explanation,
        "raw_excerpt": r.raw_excerpt,
        "status": r.status,
        "resolved_at": r.resolved_at,
        "corrected_values": r.corrected_values,
    }
