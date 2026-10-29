"""Simulated temperature sensors -> MQTT."""
from __future__ import annotations

import json
import logging
import os
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sensors")

MQTT_HOST = os.environ.get("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
PUBLISH_INTERVAL = float(os.environ.get("SENSOR_INTERVAL", "5"))


def main() -> None:
    import paho.mqtt.client as mqtt
    import redis as redis_lib

    from app.devices import DEVICES, generate_telemetry

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sim-sensors")
    connected = False
    for attempt in range(30):
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_start()
            connected = True
            logger.info("Connected to MQTT at %s:%d", MQTT_HOST, MQTT_PORT)
            break
        except Exception as exc:
            logger.warning("MQTT connect attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2)

    if not connected:
        logger.error("Could not connect to MQTT after 30 attempts, exiting")
        return

    r = None
    for attempt in range(10):
        try:
            r = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
            r.ping()
            logger.info("Connected to Redis")
            break
        except Exception as exc:
            logger.warning("Redis connect attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2)

    if r is None:
        logger.error("Could not connect to Redis, running without fault detection")

    # Set H4 ILR offline on startup (default state)
    if r:
        try:
            if not r.exists("sim:ilr_h4_online"):
                r.set("sim:ilr_h4_online", "0")
                logger.info("Set sim:ilr_h4_online=0 (H4 ILR offline by default)")
        except Exception:
            pass

    logger.info("Starting sensor loop, %d devices, interval %.1fs", len(DEVICES), PUBLISH_INTERVAL)

    try:
        while True:
            for device in DEVICES:
                payload = generate_telemetry(device, r)
                topic = f"district/coldchain/{device.device_id}/telemetry"
                client.publish(topic, json.dumps(payload), qos=0)
            time.sleep(PUBLISH_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
