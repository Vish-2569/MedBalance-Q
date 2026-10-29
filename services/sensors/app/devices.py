"""Device inventory and per-device telemetry state."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

FAULT_TARGET_TEMP = 11.0
FAULT_RAMP_CYCLES = 12
NORMAL_BASE_TEMP = 4.5
NORMAL_NOISE_STD = 1.0
NORMAL_TEMP_MIN = 2.0
NORMAL_TEMP_MAX = 8.0


@dataclass
class Device:
    device_id: str
    vehicle_id: str | None = None
    facility_id: str | None = None
    kind: str = "vehicle"  # "vehicle" or "ilr"

    # mutable state
    battery: float = field(default=95.0, repr=False)
    fault_cycle: int = field(default=0, repr=False)
    in_fault: bool = field(default=False, repr=False)
    _pre_fault_temp: float = field(default=NORMAL_BASE_TEMP, repr=False)

    def generate_normal(self) -> dict:
        temp = NORMAL_BASE_TEMP + random.gauss(0, NORMAL_NOISE_STD)
        temp = max(NORMAL_TEMP_MIN, min(NORMAL_TEMP_MAX, temp))
        door_open = random.random() < 0.02
        self.battery = max(60.0, self.battery - 0.01)
        return {
            "ts": datetime.now(IST).isoformat(timespec="seconds"),
            "temp_c": round(temp, 2),
            "door_open": door_open,
            "battery": round(self.battery, 1),
        }

    def generate_fault(self) -> dict:
        if self.fault_cycle == 0:
            self._pre_fault_temp = NORMAL_BASE_TEMP + random.gauss(0, 0.3)
        step = (FAULT_TARGET_TEMP - self._pre_fault_temp) / FAULT_RAMP_CYCLES
        self.fault_cycle = min(self.fault_cycle + 1, FAULT_RAMP_CYCLES)
        temp = self._pre_fault_temp + step * self.fault_cycle + random.gauss(0, 0.2)
        self.battery = max(60.0, self.battery - 0.01)
        return {
            "ts": datetime.now(IST).isoformat(timespec="seconds"),
            "temp_c": round(temp, 2),
            "door_open": False,
            "battery": round(self.battery, 1),
        }

    def generate_offline(self) -> dict:
        return {
            "ts": datetime.now(IST).isoformat(timespec="seconds"),
            "temp_c": None,
            "door_open": None,
            "battery": None,
            "offline": True,
        }

    def clear_fault(self) -> None:
        self.in_fault = False
        self.fault_cycle = 0


DEVICES: list[Device] = [
    Device(device_id="sensor-cv01-a", vehicle_id="CV-01", kind="vehicle"),
    Device(device_id="sensor-cv01-b", vehicle_id="CV-01", kind="vehicle"),
    Device(device_id="sensor-cv02-a", vehicle_id="CV-02", kind="vehicle"),
    Device(device_id="sensor-ilr-h1", facility_id="H1", kind="ilr"),
    Device(device_id="sensor-ilr-h2", facility_id="H2", kind="ilr"),
    Device(device_id="sensor-ilr-h3", facility_id="H3", kind="ilr"),
    Device(device_id="sensor-ilr-h4", facility_id="H4", kind="ilr"),
]


def get_faulted_vehicles(redis_client) -> set[str]:
    """Read sim:device_faults from Redis, return set of vehicle IDs in fault."""
    try:
        raw = redis_client.get("sim:device_faults")
        if not raw:
            return set()
        faults = json.loads(raw)
        return {f["device_id"] for f in faults if "device_id" in f}
    except Exception:
        return set()


def is_ilr_h4_online(redis_client) -> bool:
    """H4 ILR is online only after ilr_repaired sets the key."""
    try:
        val = redis_client.get("sim:ilr_h4_online")
        return val is not None and val not in (b"0", b"false", b"", "0", "false", "")
    except Exception:
        return False


def generate_telemetry(device: Device, redis_client) -> dict:
    """Produce one telemetry reading for a device given current Redis state."""
    # H4 ILR offline logic
    if device.device_id == "sensor-ilr-h4" and not is_ilr_h4_online(redis_client):
        return device.generate_offline()

    # Vehicle fault logic
    if device.vehicle_id:
        faulted = get_faulted_vehicles(redis_client)
        if device.vehicle_id in faulted:
            device.in_fault = True
            return device.generate_fault()
        elif device.in_fault:
            device.clear_fault()

    return device.generate_normal()
