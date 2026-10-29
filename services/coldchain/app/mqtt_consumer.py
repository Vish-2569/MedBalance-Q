"""MQTT subscriber that feeds the cold-chain state machines."""
from __future__ import annotations

import json
import logging
import threading
from urllib.parse import urlparse

from .device_registry import DEVICES
from .state_machine import DeviceStateMachine
from .store import TelemetryStore

logger = logging.getLogger(__name__)

TOPIC = "district/coldchain/+/telemetry"

_machines: dict[str, DeviceStateMachine] = {}
_store = TelemetryStore()
_alert_callback = None


def get_store() -> TelemetryStore:
    return _store


def get_machines() -> dict[str, DeviceStateMachine]:
    return _machines


def set_alert_callback(cb) -> None:
    global _alert_callback
    _alert_callback = cb


def init_machines() -> None:
    _machines.clear()
    for dev_id, cfg in DEVICES.items():
        _machines[dev_id] = DeviceStateMachine(
            device_id=dev_id,
            vehicle_id=cfg.vehicle_id,
            facility_id=cfg.facility_id,
        )


def _on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Bad MQTT payload on %s", msg.topic)
        return

    parts = msg.topic.split("/")
    if len(parts) < 4:
        return
    device_id = parts[2]

    ts = payload.get("ts", "")
    temp_c = payload.get("temp_c")
    door_open = payload.get("door_open", False)
    battery = payload.get("battery", 100)

    machine = _machines.get(device_id)
    if machine is None:
        logger.debug("Unknown device %s, ignoring", device_id)
        return

    events = machine.process_reading(ts, temp_c, door_open, battery)

    _store.append(device_id, ts, temp_c, door_open, battery, machine.state)

    for ev in events:
        logger.info("Cold-chain event: %s %s", ev["type"], device_id)
        if _alert_callback:
            try:
                _alert_callback(ev)
            except Exception:
                logger.exception("Alert callback failed for %s", device_id)


def start_mqtt(mqtt_url: str) -> threading.Thread:
    """Start paho-mqtt in a background daemon thread."""
    import paho.mqtt.client as mqtt

    parsed = urlparse(mqtt_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 1883

    def _on_connect(client, userdata, flags, rc, properties=None):
        logger.info("MQTT connected (rc=%s), subscribing to %s", rc, TOPIC)
        client.subscribe(TOPIC)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = _on_connect
    client.on_message = _on_message

    def _run():
        try:
            client.connect(host, port, keepalive=60)
            client.loop_forever()
        except Exception:
            logger.exception("MQTT loop crashed")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
