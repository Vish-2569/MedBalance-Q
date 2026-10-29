from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from medbal_common.logging import setup_logging, get_logger
from medbal_common.settings import settings


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
        result: dict = {"status": "ok", "service": name}
        if keys:
            ks = settings.key_status()
            result["keys"] = {k: ks[k] for k in keys if k in ks}
        return result

    return app
