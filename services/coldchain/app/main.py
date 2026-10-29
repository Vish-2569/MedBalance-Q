import logging
from contextlib import asynccontextmanager

from medbal_common.fastapi_base import create_app
from medbal_common.settings import settings

logger = logging.getLogger(__name__)

app = create_app("coldchain")

if settings.USE_FIXTURES:
    from medbal_common.fixtures import serve

    serve(app, "coldchain")
else:
    from . import mqtt_consumer
    from .routers import status

    def _publish_alert(event: dict) -> None:
        try:
            from medbal_common.bus import publish

            alert_payload = {
                "device_id": event["device_id"],
                "vehicle_id": event.get("vehicle_id"),
                "route_ids": [],
                "temp_c": event.get("temp_c"),
                "since": event.get("since"),
                "severity": event.get("severity", "critical"),
            }
            publish("coldchain.alert", alert_payload)
            logger.info("Published coldchain.alert for %s", event["device_id"])
        except Exception:
            logger.exception("Failed to publish coldchain.alert")

    @asynccontextmanager
    async def lifespan(a):
        mqtt_consumer.init_machines()
        mqtt_consumer.set_alert_callback(_publish_alert)
        try:
            mqtt_consumer.start_mqtt(settings.MQTT_URL)
            logger.info("MQTT consumer started for cold-chain")
        except Exception:
            logger.warning("MQTT not available, running without sensor feed")
        yield

    app.router.lifespan_context = lifespan
    app.include_router(status.router)
