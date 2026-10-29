"""Gate: routes clean items to core-api upsert and flagged items to review queue."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date

import httpx

from medbal_common.logging import get_logger

from .adapters import ExtractionItem
from .anomaly import check_anomalies, build_fallback_explanation

log = get_logger("ingest-ai.gate")

CORE_API_URL_DEFAULT = "http://core-api:8001"
GENAI_URL_DEFAULT = "http://genai:8003"


@dataclass
class GateResult:
    clean_count: int = 0
    flagged_count: int = 0
    upserted: int = 0
    review_ids: list[str] = field(default_factory=list)


async def _fetch_context(
    facility_code: str, core_api_url: str
) -> tuple[dict[str, int], dict[str, list[dict]]]:
    """Fetch typical quantities and lots from core-api. Returns (typical_qty_by_drug, lots_by_batch)."""
    typical_qty: dict[str, int] = {}
    lots_by_batch: dict[str, list[dict]] = {}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            pos_resp = await client.get(f"{core_api_url}/positions", params={"facility": facility_code})
            if pos_resp.status_code == 200:
                for pos in pos_resp.json():
                    code = pos.get("drug_code")
                    stock = pos.get("effective_stock", 0)
                    if code:
                        typical_qty[code] = stock

            lots_resp = await client.get(f"{core_api_url}/lots", params={"facility": facility_code})
            if lots_resp.status_code == 200:
                for lot in lots_resp.json():
                    batch = lot.get("batch_no")
                    if batch:
                        lots_by_batch.setdefault(batch, []).append(lot)
    except Exception as exc:
        log.warning("context_fetch_failed", facility=facility_code, error=str(exc))

    return typical_qty, lots_by_batch


async def _get_llm_explanation(
    item: ExtractionItem,
    rules: list[str],
    facility_code: str,
    raw_excerpt: str | None,
    typical_qty: int | None,
    genai_url: str,
) -> str:
    """Call genai for anomaly explanation, fall back to template."""
    today = _get_today()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{genai_url}/llm/complete",
                json={
                    "purpose": "anomaly_explain",
                    "prompt_id": "anomaly_explain",
                    "version": 1,
                    "input": {
                        "facility_code": facility_code,
                        "item": item.to_dict(),
                        "rules": rules,
                        "typical_qty": typical_qty,
                        "raw_excerpt": (raw_excerpt or "")[:500],
                    },
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                explanation = data.get("output", {}).get("explanation")
                if explanation:
                    return explanation
    except Exception as exc:
        log.warning("llm_explain_failed", error=str(exc))

    return build_fallback_explanation(item, rules, today, typical_qty)


def _get_today() -> date:
    try:
        from medbal_common.clock import today
        return today()
    except Exception:
        return date.today()


def _can_upsert(item: ExtractionItem) -> bool:
    return bool(
        item.drug_code
        and item.batch_no
        and item.expiry
        and item.qty is not None
        and item.qty > 0
    )


async def _upsert_clean(
    items: list[ExtractionItem], facility_code: str, core_api_url: str
) -> int:
    """POST clean items to core-api /lots/upsert-batch."""
    upsertable = [i for i in items if _can_upsert(i)]
    if not upsertable:
        return 0

    payload = [
        {
            "facility_id": facility_code,
            "drug_code": i.drug_code,
            "batch_no": i.batch_no,
            "expiry": i.expiry,
            "qty": i.qty,
        }
        for i in upsertable
    ]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{core_api_url}/lots/upsert-batch", json=payload)
            if resp.status_code == 200:
                return resp.json().get("upserted", 0)
            log.warning("upsert_failed", status=resp.status_code)
    except Exception as exc:
        log.warning("upsert_error", error=str(exc))

    return 0


def _publish_event(stream: str, data: dict) -> None:
    try:
        from medbal_common.bus import publish
        publish(stream, data)
    except Exception as exc:
        log.debug("event_publish_skipped", stream=stream, error=str(exc))


async def run_gate(
    report_id: str,
    items: list[ExtractionItem],
    facility_code: str,
    raw_text: str | None = None,
    *,
    core_api_url: str | None = None,
    genai_url: str | None = None,
) -> GateResult:
    """Run anomaly gate on items. Clean → core-api upsert, flagged → review queue."""
    from .review import add_review

    core_url = core_api_url or os.environ.get("CORE_API_URL", CORE_API_URL_DEFAULT)
    gen_url = genai_url or os.environ.get("GENAI_URL", GENAI_URL_DEFAULT)
    today = _get_today()

    typical_qty_map, lots_by_batch = await _fetch_context(facility_code, core_url)

    clean: list[ExtractionItem] = []
    flagged: list[tuple[int, ExtractionItem, list[str]]] = []

    for idx, item in enumerate(items):
        rules = check_anomalies(
            item,
            facility_code,
            today,
            typical_qty=typical_qty_map.get(item.drug_code or ""),
            lots_by_batch=lots_by_batch,
        )
        if rules:
            flagged.append((idx, item, rules))
        else:
            clean.append(item)

    result = GateResult()

    result.upserted = await _upsert_clean(clean, facility_code, core_url)
    result.clean_count = len(clean)

    for idx, item, rules in flagged:
        typical = typical_qty_map.get(item.drug_code or "")
        explanation = await _get_llm_explanation(
            item, rules, facility_code, raw_text, typical, gen_url,
        )
        review_id = add_review(
            report_id=report_id,
            facility_code=facility_code,
            item_index=idx,
            extraction=item.to_dict(),
            anomaly_rules=rules,
            explanation=explanation,
            raw_excerpt=(raw_text or "")[:500] if raw_text else None,
        )
        result.review_ids.append(review_id)

        _publish_event("anomaly.flagged", {
            "report_id": report_id,
            "item_index": idx,
            "anomaly_type": rules[0],
            "severity": "high" if "unknown_drug" in rules else "medium",
            "details": {"rules": rules, "review_id": review_id},
        })

    result.flagged_count = len(flagged)

    _publish_event("report.received", {
        "report_id": report_id,
        "facility_code": facility_code,
        "clean": result.clean_count,
        "flagged": result.flagged_count,
    })

    log.info(
        "gate_complete",
        report_id=report_id,
        clean=result.clean_count,
        flagged=result.flagged_count,
        upserted=result.upserted,
    )

    return result
