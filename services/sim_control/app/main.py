from medbal_common.fastapi_base import create_app
from medbal_common.settings import settings

app = create_app("sim-control")

if settings.USE_FIXTURES:
    from medbal_common.fixtures import serve
    serve(app, "sim-control")
else:
    from .clock_state import tick_lifespan
    from .routers import clock as clock_router
    from .routers import scenarios as scenarios_router

    app.router.lifespan_context = tick_lifespan
    app.include_router(clock_router.router)
    app.include_router(scenarios_router.router)
