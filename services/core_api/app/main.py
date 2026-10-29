from medbal_common.fastapi_base import create_app
from medbal_common.settings import settings

app = create_app("core-api")

if settings.USE_FIXTURES:
    from medbal_common.fixtures import serve
    serve(app, "core-api")
else:
    from .routers import master, lots, positions, snapshot, plans, orders
    from .routers import provenance, audit_routes, custody, events

    app.include_router(master.router)
    app.include_router(lots.router)
    app.include_router(positions.router)
    app.include_router(snapshot.router)
    app.include_router(plans.router)
    app.include_router(orders.router)
    app.include_router(provenance.router)
    app.include_router(audit_routes.router)
    app.include_router(custody.router)
    app.include_router(events.router)
