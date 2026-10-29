from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from medbal_common.logging import setup_logging, get_logger
from medbal_common.settings import settings


def _check_postgres() -> str:
    try:
        from sqlalchemy import text
        from medbal_common.db import get_engine
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "degraded"


def _check_redis() -> str:
    try:
        from medbal_common.bus import get_redis
        get_redis().ping()
        return "ok"
    except Exception:
        return "degraded"


def create_app(name: str, keys: list[str] | None = None) -> FastAPI:
    setup_logging(name)
    log = get_logger(name)
    app = FastAPI(title=f"MedBalance-Q — {name}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        log.info("request", method=request.method, path=request.url.path)
        response = await call_next(request)
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.error("unhandled_exception", exc=str(exc))
        return JSONResponse(status_code=500, content={"error": str(exc)})

    @app.get("/health")
    async def health():
        degraded: list[str] = []
        result: dict = {"status": "ok", "service": name}
        if keys:
            ks = settings.key_status()
            result["keys"] = {k: ks[k] for k in keys if k in ks}
            for k, v in result["keys"].items():
                if v == "missing":
                    degraded.append(f"key:{k}")

        pg = _check_postgres()
        redis_st = _check_redis()
        result["postgres"] = pg
        result["redis"] = redis_st
        if pg != "ok":
            degraded.append("postgres")
        if redis_st != "ok":
            degraded.append("redis")

        result["demo_mode"] = settings.DEMO_MODE
        if degraded:
            result["status"] = "degraded"
            result["degraded"] = degraded

        return result

    return app
