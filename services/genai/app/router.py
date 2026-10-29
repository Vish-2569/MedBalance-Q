from __future__ import annotations

import json
import os
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from medbal_common.logging import get_logger
from medbal_common.settings import settings

from .copilot import CopilotSession
from .firewall import check_narration
from .narration import narrate_order, narrate_credit_memo
from .pdf_gen import generate_dta_pdf, generate_coldchain_log_pdf, generate_credit_memo_pdf

log = get_logger("genai.router")

CORE_API_URL = os.environ.get("CORE_API_URL", "http://core-api:8001")
COLDCHAIN_URL = os.environ.get("COLDCHAIN_URL", "http://coldchain:8006")


class LlmRequest(BaseModel):
    purpose: str
    prompt_id: str
    version: int
    input: dict[str, Any]


class NarrateRequest(BaseModel):
    order_facts: dict[str, Any]


class BatchNarrateRequest(BaseModel):
    orders: list[dict[str, Any]]


class CreditMemoRequest(BaseModel):
    donor_facility: dict[str, Any]
    items: list[dict[str, Any]]
    plan_id: str = ""


router = APIRouter()


@router.post("/llm/complete")
async def llm_complete(req: LlmRequest, request: Request):
    svc = request.app.state.llm_service
    result = await svc.complete(
        purpose=req.purpose,
        prompt_id=req.prompt_id,
        version=req.version,
        input_data=req.input,
    )
    return result


@router.get("/ai/health")
async def ai_health(request: Request):
    svc = request.app.state.llm_service
    stats = svc.get_health_stats()
    return {
        "status": "ok",
        "service": "genai",
        "provider": settings.LLM_PROVIDER,
        "models": {
            "fast": settings.LLM_MODEL_FAST,
            "smart": settings.LLM_MODEL_SMART,
        },
        "demo_mode": settings.DEMO_MODE,
        "prompts_loaded": len(request.app.state.prompt_list),
        "stats": stats,
    }


# ── Copilot chat (SSE streaming) ──────────────────────────────────

class CopilotRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str = "demo"


@router.post("/copilot/chat")
async def copilot_chat(req: CopilotRequest, request: Request):
    """Streaming copilot agent with tool-use. Returns SSE events."""
    svc = request.app.state.llm_service
    engine = getattr(request.app.state, "db_engine", None)
    session = CopilotSession(svc, db_engine=engine)

    async def event_stream():
        async for event in session.chat(
            session_id=req.session_id,
            message=req.message,
            user_id=req.user_id,
        ):
            yield f"data: {json.dumps(event, default=str)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Narration endpoints ───────────────────────────────────────────

@router.post("/narrate/batch")
async def narrate_batch(req: BatchNarrateRequest, request: Request):
    """Generate narrations for a batch of orders (called on plan.completed)."""
    svc = request.app.state.llm_service
    results = []
    for order_facts in req.orders:
        result = await narrate_order(svc, order_facts)
        result["order_id"] = order_facts.get("order_id", "")
        results.append(result)
    return {"narrations": results}


@router.post("/narrate/{order_id}")
async def narrate_single(order_id: str, req: NarrateRequest, request: Request):
    """Generate grounded narration for a single order."""
    svc = request.app.state.llm_service
    result = await narrate_order(svc, req.order_facts)
    result["order_id"] = order_id
    return result


# ── DTA voucher PDF ───────────────────────────────────────────────

@router.get("/dta/{order_id}/pdf")
async def dta_pdf(order_id: str):
    """Generate and return a DTA voucher PDF for an order."""
    order = await _fetch_order(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    base_url = os.environ.get("PUBLIC_URL", "http://localhost:8080/api/core")
    pdf_bytes = generate_dta_pdf(order, base_url=base_url)

    content_type = "application/pdf"
    if not pdf_bytes or pdf_bytes[:4] == b"<!DO":
        content_type = "text/html"

    return Response(
        content=pdf_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="DTA-{order.get("dta_number", order_id)}.pdf"',
        },
    )


# ── Cold-chain consignment log PDF ────────────────────────────────

@router.get("/coldchain-log/{order_id}/pdf")
async def coldchain_log_pdf(order_id: str):
    """Generate cold-chain consignment log PDF for a cold order."""
    order = await _fetch_order(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    if order.get("temperature_req") != "cold_chain":
        return {"error": "Not a cold-chain order"}

    readings = await _fetch_coldchain_readings(order)

    pdf_bytes = generate_coldchain_log_pdf(order, readings)

    content_type = "application/pdf"
    if not pdf_bytes or pdf_bytes[:4] == b"<!DO":
        content_type = "text/html"

    return Response(
        content=pdf_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="ColdChain-{order_id}.pdf"',
        },
    )


# ── Credit memo PDF ──────────────────────────────────────────────

@router.post("/credit-memo/pdf")
async def credit_memo_pdf(req: CreditMemoRequest, request: Request):
    """Generate donor credit memo PDF."""
    svc = request.app.state.llm_service

    total_units = sum(i.get("qty", 0) for i in req.items)
    total_value = sum(i.get("value_inr", 0) for i in req.items)

    memo_facts = {
        "donor_facility": req.donor_facility.get("name", ""),
        "donor_facility_id": req.donor_facility.get("id", ""),
        "total_units": total_units,
        "value_inr": round(total_value, 2),
        "drugs_summary": ", ".join(set(i.get("drug_name", "") for i in req.items)),
        "transfer_count": len(req.items),
        "receivers": ", ".join(set(i.get("dst_facility", "") for i in req.items)),
        "unit": "units",
    }

    memo_result = await narrate_credit_memo(svc, memo_facts)
    paragraph = memo_result.get("paragraph", "")

    pdf_bytes = generate_credit_memo_pdf(
        req.donor_facility, req.items,
        paragraph=paragraph, plan_id=req.plan_id,
    )

    content_type = "application/pdf"
    if not pdf_bytes or pdf_bytes[:4] == b"<!DO":
        content_type = "text/html"

    return Response(
        content=pdf_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="CreditMemo-{req.donor_facility.get("id", "")}.pdf"',
        },
    )


# ── Helpers ───────────────────────────────────────────────────────

async def _fetch_order(order_id: str) -> dict[str, Any] | None:
    """Fetch order details from core-api."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{CORE_API_URL}/orders/{order_id}")
            if resp.status_code == 200:
                return resp.json()
    except Exception as exc:
        log.warning("fetch_order_failed", order_id=order_id, error=str(exc))

    if settings.USE_FIXTURES:
        return _fixture_order(order_id)
    return None


async def _fetch_coldchain_readings(order: dict[str, Any]) -> list[dict[str, Any]]:
    """Fetch sensor readings from coldchain service for the order's route."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{COLDCHAIN_URL}/status")
            if resp.status_code == 200:
                devices = resp.json()
                readings = []
                for d in devices:
                    history = d.get("history", [])
                    for r in history:
                        readings.append({
                            "timestamp": r.get("timestamp", ""),
                            "temp_c": r.get("temp_c"),
                            "humidity": r.get("humidity"),
                        })
                return readings
    except Exception as exc:
        log.warning("fetch_readings_failed", error=str(exc))

    return [
        {"timestamp": "2026-10-30T08:00:00", "temp_c": 4.2, "humidity": 45},
        {"timestamp": "2026-10-30T08:05:00", "temp_c": 4.5, "humidity": 44},
        {"timestamp": "2026-10-30T08:10:00", "temp_c": 4.1, "humidity": 46},
    ]


def _fixture_order(order_id: str) -> dict[str, Any] | None:
    """Return a fixture order for testing."""
    import json
    from pathlib import Path
    try:
        p = Path("/app/contracts/fixtures/plan-demo.json")
        if not p.exists():
            p = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "plan-demo.json"
        if not p.exists():
            p = Path(__file__).resolve().parents[3] / "contracts" / "fixtures" / "plan-demo.json"
        if p.exists():
            data = json.loads(p.read_text())
            for o in data.get("orders", []):
                if o.get("id") == order_id:
                    return o
    except Exception:
        pass
    return None
