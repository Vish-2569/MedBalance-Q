from medbal_common.fastapi_base import create_app
from medbal_common.settings import settings

from .router import router

app = create_app("forecast")

# Router first so real endpoints take priority over fixture stubs
app.include_router(router)

if settings.USE_FIXTURES:
    from medbal_common.fixtures import serve
    serve(app, "forecast")
