from contextlib import asynccontextmanager

from medbal_common.fastapi_base import create_app
from medbal_common.logging import get_logger
from medbal_common.settings import settings

from .router import router

log = get_logger("optimizer.main")


@asynccontextmanager
async def _lifespan(app):
    if not settings.USE_FIXTURES:
        try:
            from medbal_common.bus import stream_lifespan
            from .replan import handle_coldchain_alert

            async with stream_lifespan(
                "coldchain.alert",
                "optimizer-replan",
                "optimizer-1",
                handle_coldchain_alert,
            ):
                yield
        except Exception as exc:
            log.warning("coldchain_consumer_failed", error=str(exc))
            yield
    else:
        yield


app = create_app("optimizer", keys=["QPIAI_OPT_URL", "QPIAI_QCLOUD_API_KEY"])
app.router.lifespan_context = _lifespan

app.include_router(router)

if settings.USE_FIXTURES:
    from medbal_common.fixtures import serve
    serve(app, "optimizer")
