"""Ingest-AI API routes: push endpoint, pull trigger, reports list, review queue."""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from medbal_common.logging import get_logger

from .adapters import get_adapter, FACILITY_STYLE
from .extraction import extract_from_text, GENAI_URL_DEFAULT
from .gate import run_gate
from .grounding import ground_drugs_batch
from .review import list_reviews, resolve_review, get_aliases

log = get_logger("ingest-ai")

router = APIRouter()

_reports: list[dict] = []
_demo_seed_lock = asyncio.Lock()

PULL_CONFIGS: dict[str, dict] = {
    "H1": {"style": "fhir", "url": "http://sim-hospital-h1:8101/fhir/InventoryReport"},
    "H2": {"style": "csv", "url": "http://sim-hospital-h2:8101/export/stock.csv"},
}

_LLM_FORMATS = {"chat", "text"}


class ResolveBody(BaseModel):
    action: str
    corrected_values: dict | None = None


def _genai_url() -> str:
    return os.environ.get("GENAI_URL", GENAI_URL_DEFAULT)


async def _process_report(
    facility_code: str,
    payload: dict | str,
    *,
    is_demo: bool = False,
) -> dict:
    report = get_adapter(facility_code).parse(facility_code, payload)

    if report.format in _LLM_FORMATS and report.raw_text:
        try:
            report.items = await extract_from_text(
                report.raw_text,
                report.reported_at[:10],
                facility_code,
                genai_url=_genai_url(),
            )
            if report.items:
                methods = {item.extraction_method for item in report.items}
                report.extraction_method = (
                    "deterministic_fallback"
                    if "deterministic_fallback" in methods
                    else "genai"
                )
                if report.extraction_method == "deterministic_fallback":
                    report.extraction_warning = (
                        "GenAI did not return usable items; explicit values were "
                        "extracted with the deterministic fallback."
                    )
        except Exception as exc:
            log.warning(
                "extraction_error",
                facility=facility_code,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            report.extraction_warning = (
                "Text extraction failed; the raw report is saved and ingest-ai logs "
                "contain the error."
            )

    if report.items:
        ground_drugs_batch(report.items)

    report_dict = report.to_dict()
    report_dict["id"] = str(uuid.uuid4())
    if is_demo:
        report_dict["is_demo"] = True

    gate_result = None
    gate_error = False
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
            gate_error = True
            log.warning(
                "gate_error",
                facility=facility_code,
                error_type=type(exc).__name__,
                error=str(exc),
            )

    if gate_result:
        report_dict["gate"] = {
            "clean": gate_result.clean_count,
            "flagged": gate_result.flagged_count,
            "upserted": gate_result.upserted,
            "review_ids": gate_result.review_ids,
        }
    else:
        report_dict["gate"] = {
            "clean": 0,
            "flagged": 0,
            "upserted": 0,
            "review_ids": [],
        }
    if gate_error:
        report_dict["gate_error"] = "Could not complete the review gate; see ingest-ai logs."

    _reports.insert(0, report_dict)
    log.info(
        "report_ingested",
        facility=facility_code,
        format=report.format,
        items=len(report.items),
        extraction_method=report.extraction_method,
    )
    return report_dict


@router.post("/ingest/{facility_code}")
async def ingest_report(facility_code: str, request: Request):
    if facility_code not in FACILITY_STYLE:
        return JSONResponse(
            status_code=400,
            content={"error": f"unknown facility {facility_code}"},
        )

    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        payload = await request.json()
    else:
        payload = (await request.body()).decode("utf-8")

    return await _process_report(facility_code, payload)


@router.post("/demo/seed")
async def seed_demo_reports():
    async with _demo_seed_lock:
        return await _seed_demo_reports()


async def _seed_demo_reports():
    from medbal_common.clock import today

    report_date = today()
    expiry_future = (report_date + timedelta(days=180)).isoformat()
    expiry_past = (report_date - timedelta(days=30)).isoformat()
    samples = [
        (
            "H3",
            "chat",
            "\n".join([
                "ನಮಸ್ಕಾರ ಸರ್, ಇಂದಿನ stock update:",
                f"- ಇನ್ಸುಲಿನ್ 40IU - 20 vials, batch SIM-IN-001, exp {expiry_future}",
                f"- paracetamol 500 - 120 tablets, batch SIM-PCM-001, exp {expiry_future}",
                f"- ORS 30 sachets, batch SIM-ORS-001, exp {expiry_future}",
            ]),
        ),
        (
            "H4",
            "text",
            "\n".join([
                f"SIM-H4 stock register {report_date.isoformat()}",
                f"inzulin - 10000 vial batch SIM-BAD-001 exp {expiry_past}",
                f"amoxy 500 cap - 7 strip batch SIM-AMX-001 exp {expiry_future}",
            ]),
        ),
    ]

    results = []
    for facility_code, report_format, body in samples:
        existing = next(
            (
                report for report in _reports
                if report.get("is_demo") and report.get("raw_text") == body
            ),
            None,
        )
        report = existing or await _process_report(
            facility_code,
            {
                "facility_id": facility_code,
                "date": report_date.isoformat(),
                "format": report_format,
                "body": body,
            },
            is_demo=True,
        )
        results.append({
            "id": report["id"],
            "facility_code": facility_code,
            "items": len(report["items"]),
            "extraction_method": report.get("extraction_method"),
        })

    return {"triggered": len(results), "reports": results}


@router.post("/pull/run")
async def pull_run():
    import httpx

    triggered = 0
    facilities: list[str] = []
    reports: list[dict] = []
    errors: list[dict[str, str]] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for fac_code, cfg in PULL_CONFIGS.items():
            try:
                resp = await client.get(cfg["url"])
                resp.raise_for_status()

                style = FACILITY_STYLE[fac_code]
                if style == "fhir":
                    payload = resp.json()
                else:
                    payload = resp.text

                report_dict = await _process_report(fac_code, payload)
                triggered += 1
                facilities.append(fac_code)
                reports.append({
                    "id": report_dict["id"],
                    "facility_code": fac_code,
                    "items": len(report_dict["items"]),
                    "extraction_method": report_dict.get("extraction_method"),
                })
            except Exception as exc:
                log.error("pull_failed", facility=fac_code, error=str(exc))
                errors.append({"facility_code": fac_code, "error": str(exc)})

    if errors and not triggered:
        return JSONResponse(
            status_code=502,
            content={"triggered": 0, "facilities": [], "reports": [], "errors": errors},
        )
    return {
        "triggered": triggered,
        "facilities": facilities,
        "reports": reports,
        "errors": errors,
    }


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
