"""Hardcoded device-to-vehicle/facility mapping."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceConfig:
    device_id: str
    vehicle_id: str | None = None
    facility_id: str | None = None


DEVICES: dict[str, DeviceConfig] = {
    "sensor-cv01-a": DeviceConfig("sensor-cv01-a", vehicle_id="CV-01"),
    "sensor-cv01-b": DeviceConfig("sensor-cv01-b", vehicle_id="CV-01"),
    "sensor-cv02-a": DeviceConfig("sensor-cv02-a", vehicle_id="CV-02"),
    "sensor-ilr-h1": DeviceConfig("sensor-ilr-h1", facility_id="H1"),
    "sensor-ilr-h2": DeviceConfig("sensor-ilr-h2", facility_id="H2"),
    "sensor-ilr-h3": DeviceConfig("sensor-ilr-h3", facility_id="H3"),
    "sensor-ilr-h4": DeviceConfig("sensor-ilr-h4", facility_id="H4"),
}
