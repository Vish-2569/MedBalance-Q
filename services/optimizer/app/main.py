from medbal_common.fastapi_base import create_app
from medbal_common.settings import settings

from .router import router

app = create_app("optimizer", keys=["QPIAI_OPT_URL", "QPIAI_QCLOUD_API_KEY"])

# Router first so our endpoints take priority over fixture stubs
app.include_router(router)

if settings.USE_FIXTURES:
    from medbal_common.fixtures import serve
    serve(app, "optimizer")
