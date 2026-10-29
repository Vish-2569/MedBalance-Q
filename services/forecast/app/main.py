from medbal_common.fastapi_base import create_app
from medbal_common.settings import settings

app = create_app("forecast")

if settings.USE_FIXTURES:
    from medbal_common.fixtures import serve
    serve(app, "forecast")
