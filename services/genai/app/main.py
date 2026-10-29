from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from medbal_common.fastapi_base import create_app as _create_base
from medbal_common.logging import get_logger
from medbal_common.settings import settings

from . import prompt_registry
from .cache import LLMCache
from .llm_service import LLMService
from .narration import narrate_order
from .providers import FakeProvider, GeminiProvider, LLMProvider
from .router import router

log = get_logger("genai")


def _build_provider() -> LLMProvider:
    if settings.has_gemini():
        return GeminiProvider(api_key=settings.GEMINI_API_KEY)
    log.warning("no_gemini_key", msg="falling back to FakeProvider")
    return FakeProvider()


def _build_cache() -> LLMCache:
    try:
        import redis
        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.ping()
        return LLMCache(redis_client=r)
    except Exception:
        log.warning("redis_unavailable", msg="LLM cache disabled")
        return LLMCache(redis_client=None)


def _build_engine():
    try:
        from medbal_common.db import get_engine
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return engine
    except Exception:
        log.warning("db_unavailable", msg="LLM call logging disabled")
        return None


async def _handle_plan_event(msg: dict[str, Any], app_ref: Any) -> None:
    """Batch-narrate orders when a plan completes or is revised."""
    plan_id = msg.get("plan_id", "")
    transfers = msg.get("transfers", [])
    if not transfers:
        log.info("plan_event_no_transfers", plan_id=plan_id)
        return

    svc = app_ref.state.llm_service
    for order_facts in transfers:
        try:
            result = await narrate_order(svc, order_facts)
            log.info(
                "batch_narration",
                order_id=order_facts.get("order_id", ""),
                grounding_ok=result.get("grounding_ok"),
            )
        except Exception as exc:
            log.warning("batch_narration_failed", error=str(exc))


def create_app():
    app = _create_base("genai", keys=["GEMINI_API_KEY"])

    prompt_registry.load_all()
    app.state.prompt_list = prompt_registry.list_prompts()
    log.info("prompts_loaded", count=len(app.state.prompt_list), refs=app.state.prompt_list)

    provider = _build_provider()
    cache = _build_cache()
    engine = _build_engine()

    app.state.llm_service = LLMService(
        provider=provider,
        cache=cache,
        db_engine=engine,
    )
    app.state.db_engine = engine
    log.info("llm_service_ready", provider=provider.name())

    if settings.USE_FIXTURES:
        from medbal_common.fixtures import serve
        serve(app, "genai")

    try:
        from medbal_common.bus import stream_lifespan

        plan_handler = lambda msg: asyncio.ensure_future(
            _handle_plan_event(msg, app)
        )

        @asynccontextmanager
        async def lifespan(a):
            async with stream_lifespan(
                "plan.completed", "genai-narrate", "genai-0", plan_handler
            ):
                async with stream_lifespan(
                    "plan.revised", "genai-narrate-rev", "genai-0", plan_handler
                ):
                    yield

        app.router.lifespan_context = lifespan
        log.info("narration_consumer_registered")
    except Exception as exc:
        log.warning("bus_consumer_setup_failed", error=str(exc))

    app.include_router(router)
    return app


app = create_app()
