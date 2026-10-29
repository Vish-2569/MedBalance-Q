import os
from contextlib import asynccontextmanager

from medbal_common.fastapi_base import create_app
from medbal_common.settings import settings

hospital_id = os.environ.get("HOSPITAL_ID", "h1")
app = create_app(f"sim-hospital-{hospital_id}")

if settings.USE_FIXTURES:
    from medbal_common.fixtures import serve

    serve(app, "sim-hospital")
else:
    from . import stock_db
    from .routers import state, transfers, reports
    from .tick_handler import handle_tick

    @asynccontextmanager
    async def lifespan(a):
        stock_db.init_db()
        stock_db.load_seed(hospital_id)
        try:
            from medbal_common.bus import stream_lifespan

            async with stream_lifespan(
                "clock.tick",
                "sim-hospital",
                f"sim-hospital-{hospital_id}",
                handle_tick,
            ):
                yield
        except Exception:
            yield

    app.router.lifespan_context = lifespan
    app.include_router(state.router)
    app.include_router(transfers.router)
    app.include_router(reports.router)
