from medbal_common.fastapi_base import create_app
from medbal_common.settings import settings

app = create_app("ingest-ai")

from .router import router
app.include_router(router)
