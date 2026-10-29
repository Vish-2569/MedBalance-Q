from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from medbal_common.logging import get_logger
from medbal_common.settings import settings

log = get_logger("genai.router")


class LlmRequest(BaseModel):
    purpose: str
    prompt_id: str
    version: int
    input: dict[str, Any]


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
