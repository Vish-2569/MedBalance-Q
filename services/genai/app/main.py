from __future__ import annotations

from medbal_common.fastapi_base import create_app as _create_base
from medbal_common.logging import get_logger
from medbal_common.settings import settings

from . import prompt_registry
from .cache import LLMCache
from .llm_service import LLMService
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
    log.info("llm_service_ready", provider=provider.name())

    if settings.USE_FIXTURES:
        from medbal_common.fixtures import serve
        serve(app, "genai")

    app.include_router(router)
    return app


app = create_app()
