"""LLM-based extraction pipeline for chat/text reports."""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

import httpx

from medbal_common.logging import get_logger

from .adapters import ExtractionItem
from .grounding import ground_drug, ground_drugs_batch

log = get_logger("ingest-ai.extraction")

GENAI_URL_DEFAULT = "http://genai:8003"

_UNIT_ALIASES: dict[str, str] = {
    "strip": "tablet",
    "strips": "tablet",
    "tab": "tablet",
    "tabs": "tablet",
    "tablet": "tablet",
    "tablets": "tablet",
    "cap": "capsule",
    "caps": "capsule",
    "capsule": "capsule",
    "capsules": "capsule",
    "vial": "vial",
    "vials": "vial",
    "ampoule": "ampoule",
    "ampoules": "ampoule",
    "amp": "ampoule",
    "amps": "ampoule",
    "sachet": "sachet",
    "sachets": "sachet",
    "pkt": "sachet",
    "packet": "sachet",
    "bottle": "bottle",
    "bottles": "bottle",
    "dose": "dose",
    "doses": "dose",
    "ml": "ml",
}

_STRIP_MULTIPLIER = 10


def scan_text_for_mentions(raw_text: str) -> list[dict]:
    """Scan free text for drug name mentions using n-gram windows + grounding."""
    tokens = _tokenize(raw_text)
    seen_codes: dict[str, dict] = {}

    for width in range(1, 5):
        for i in range(len(tokens) - width + 1):
            window = " ".join(tokens[i : i + width])
            if len(window) < 2:
                continue
            result = ground_drug(window)
            if result.drug_code and result.score >= 50:
                existing = seen_codes.get(result.drug_code)
                if existing is None or result.score > existing["score"]:
                    seen_codes[result.drug_code] = {
                        "mention": window,
                        "drug_code": result.drug_code,
                        "drug_name": result.drug_name,
                        "score": result.score,
                    }

    return list(seen_codes.values())


def _tokenize(text: str) -> list[str]:
    """Split text on whitespace and punctuation, keeping Kannada tokens intact."""
    return [t for t in re.split(r"[\s,;:\-–—\(\)\[\]]+", text) if t]


async def call_genai_extract(
    raw_text: str,
    report_date: str,
    facility_code: str,
    candidates: list[dict],
    *,
    genai_url: str = GENAI_URL_DEFAULT,
) -> dict | None:
    """Call the genai gateway to extract stock items from raw text."""
    payload = {
        "purpose": "extract_stock",
        "prompt_id": "extract_stock",
        "version": 1,
        "input": {
            "raw_text": raw_text,
            "report_date": report_date,
            "facility_code": facility_code,
            "candidates": candidates,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(f"{genai_url}/llm/complete", json=payload)
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok") and data.get("output"):
                return data["output"]
            log.warning("genai_extraction_failed", error=data.get("error"))
            return None
    except Exception as exc:
        log.warning("genai_call_error", error=str(exc))
        return None


def validate_extraction(
    raw_items: list[dict],
    candidates: list[dict],
    report_date: str,
) -> list[ExtractionItem]:
    """Deterministic post-validation of LLM extraction output."""
    valid_codes = {c["drug_code"] for c in candidates}
    valid_codes.add("UNKNOWN")
    report_dt = _parse_date_safe(report_date)
    result: list[ExtractionItem] = []

    for raw in raw_items:
        flags: list[str] = []

        drug_code = raw.get("drug_code", "UNKNOWN")
        if drug_code not in valid_codes:
            flags.append("invalid_drug_code")
            drug_code = "UNKNOWN"

        raw_span = raw.get("raw_span", "")

        batch_no = raw.get("batch_no") or None
        if batch_no == "":
            batch_no = None

        expiry_raw = raw.get("expiry")
        expiry = _resolve_date(expiry_raw, report_dt)
        if expiry_raw and expiry is None:
            flags.append("invalid_date")

        qty_raw = raw.get("qty")
        unit_raw = raw.get("unit")
        unit, qty_multiplier = _normalize_unit(unit_raw)
        if unit_raw and unit is None:
            flags.append("unknown_unit")

        qty = _validate_qty(qty_raw, qty_multiplier)
        if qty is None or qty <= 0:
            flags.append("invalid_qty")
            qty = qty_raw if isinstance(qty_raw, int) and qty_raw > 0 else None

        confidence = raw.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        confidence = max(0.0, min(1.0, float(confidence)))

        result.append(ExtractionItem(
            drug_name_raw=raw_span,
            drug_code=drug_code if drug_code != "UNKNOWN" else None,
            batch_no=batch_no,
            expiry=expiry,
            qty=qty,
            unit=unit,
            confidence=confidence,
            flags=flags,
        ))

    return result


def _resolve_date(raw: str | None, report_dt: date | None) -> str | None:
    """Parse various date formats to ISO YYYY-MM-DD."""
    if not raw:
        return None
    raw = raw.strip()

    iso_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", raw)
    if iso_match:
        return raw

    mm_yyyy = re.match(r"^(\d{1,2})/(\d{4})$", raw)
    if mm_yyyy:
        month, year = int(mm_yyyy.group(1)), int(mm_yyyy.group(2))
        if 1 <= month <= 12:
            return f"{year}-{month:02d}-01"
        return None

    dd_mm = re.match(r"^(\d{1,2})/(\d{1,2})$", raw)
    if dd_mm and report_dt:
        day, month = int(dd_mm.group(1)), int(dd_mm.group(2))
        if 1 <= day <= 31 and 1 <= month <= 12:
            try:
                candidate = date(report_dt.year, month, day)
                if candidate <= report_dt:
                    candidate = date(report_dt.year + 1, month, day)
                return candidate.isoformat()
            except ValueError:
                return None

    return None


def _parse_date_safe(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return date.fromisoformat(d[:10])
    except (ValueError, TypeError):
        return None


def _normalize_unit(raw: str | None) -> tuple[str | None, int]:
    """Return (normalized_unit, qty_multiplier). Strip → tablet ×10."""
    if not raw:
        return None, 1
    key = raw.strip().lower()
    normalized = _UNIT_ALIASES.get(key)
    if normalized is None:
        return None, 1
    multiplier = _STRIP_MULTIPLIER if key in ("strip", "strips") else 1
    return normalized, multiplier


def _validate_qty(raw: Any, multiplier: int = 1) -> int | None:
    if raw is None:
        return None
    try:
        val = int(raw) * multiplier
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


async def extract_from_text(
    raw_text: str,
    report_date: str,
    facility_code: str,
    *,
    genai_url: str = GENAI_URL_DEFAULT,
) -> list[ExtractionItem]:
    """Full extraction pipeline: scan → LLM → validate → ground."""
    candidates = scan_text_for_mentions(raw_text)
    if not candidates:
        log.info("no_candidates_found", facility=facility_code)
        return []

    llm_output = await call_genai_extract(
        raw_text, report_date, facility_code, candidates, genai_url=genai_url,
    )
    if llm_output is None:
        log.warning("extraction_skipped", facility=facility_code, reason="llm_failed")
        return []

    raw_items = llm_output.get("items", [])
    if not raw_items:
        return []

    items = validate_extraction(raw_items, candidates, report_date)
    ground_drugs_batch(items)
    return items
