"""Ingest-AI API routes: push endpoint, pull trigger, reports list, review queue."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from medbal_common.logging import get_logger

from .adapters import StockReport, get_adapter, FACILITY_STYLE
from .extraction import extract_from_text, GENAI_URL_DEFAULT
from .gate import run_gate
from .grounding import ground_drugs_batch
from .review import list_reviews, resolve_review, get_aliases

log = get_logger("ingest-ai")

router = APIRouter()

_reports: list[dict] = []

PULL_CONFIGS: dict[str, dict] = {
    "H1": {"style": "fhir", "url": "http://sim-hospital-h1:8101/report"},
    "H2": {"style": "csv", "url": "http://sim-hospital-h2:8102/report"},
}

_LLM_FORMATS = {"chat", "text"}


class ResolveBody(BaseModel):
    action: str
    corrected_values: dict | None = None


def _genai_url() -> str:
    return os.environ.get("GENAI_URL", GENAI_URL_DEFAULT)


@router.post("/ingest/{facility_code}")
async def ingest_report(facility_code: str, request: Request):
    if facility_code not in FACILITY_STYLE:
        return JSONResponse(
            status_code=400,
            content={"error": f"unknown facility {facility_code}"},
        )

    adapter = get_adapter(facility_code)
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        payload = await request.json()
    else:
        payload = (await request.body()).decode("utf-8")

    report = adapter.parse(facility_code, payload)

    if report.format in _LLM_FORMATS and report.raw_text:
        try:
            items = await extract_from_text(
                report.raw_text,
                report.reported_at[:10],
                facility_code,
                genai_url=_genai_url(),
            )
            report.items = items
        except Exception as exc:
            log.warning("extraction_error", facility=facility_code, error=str(exc))

    if report.items:
        ground_drugs_batch(report.items)

    report_dict = report.to_dict()
    report_dict["id"] = str(uuid.uuid4())
    _reports.append(report_dict)

    gate_result = None
    if report.items:
        try:
            gate_result = await run_gate(
                report_id=report_dict["id"],
                items=report.items,
                facility_code=facility_code,
                raw_text=report.raw_text,
                genai_url=_genai_url(),
            )
        except Exception as exc:
            log.warning("gate_error", facility=facility_code, error=str(exc))

    log.info(
        "report_ingested",
        facility=facility_code,
        format=report.format,
        items=len(report.items),
    )

    result = report_dict
    if gate_result:
        result["gate"] = {
            "clean": gate_result.clean_count,
            "flagged": gate_result.flagged_count,
            "upserted": gate_result.upserted,
            "review_ids": gate_result.review_ids,
        }
    return result


@router.post("/pull/run")
async def pull_run():
    import httpx

    triggered = 0
    facilities: list[str] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for fac_code, cfg in PULL_CONFIGS.items():
            try:
                resp = await client.get(cfg["url"])
                resp.raise_for_status()

                adapter = get_adapter(fac_code)
                style = FACILITY_STYLE[fac_code]
                if style == "fhir":
                    payload = resp.json()
                else:
                    payload = resp.text

                report = adapter.parse(fac_code, payload)
                if report.items:
                    ground_drugs_batch(report.items)

                report_dict = report.to_dict()
                report_dict["id"] = str(uuid.uuid4())
                _reports.append(report_dict)

                triggered += 1
                facilities.append(fac_code)
                log.info("pull_ok", facility=fac_code, items=len(report.items))
            except Exception as exc:
                log.error("pull_failed", facility=fac_code, error=str(exc))

    return {"triggered": triggered, "facilities": facilities}


@router.get("/reports")
async def list_reports(facility: str | None = None, since: str | None = None):
    result = _reports
    if facility:
        result = [r for r in result if r["facility_code"] == facility]
    if since:
        result = [r for r in result if r["reported_at"] >= since]
    return result


@router.get("/reviews")
async def list_reviews_endpoint(
    facility: str | None = None,
    status: str | None = None,
    drug_code: str | None = None,
):
    return list_reviews(facility=facility, status=status, drug_code=drug_code)


@router.post("/reviews/{review_id}/resolve")
async def resolve_review_endpoint(review_id: str, body: ResolveBody):
    result = await resolve_review(
        review_id, body.action, body.corrected_values
    )
    if "error" in result:
        code = 404 if result["error"] == "not_found" else 400
        return JSONResponse(status_code=code, content=result)
    return result


@router.get("/aliases")
async def list_aliases():
    return get_aliases()
