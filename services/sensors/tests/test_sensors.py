"""Tests for sensor telemetry generation (no MQTT/Redis required)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from app.devices import (
    Device,
    DEVICES,
    generate_telemetry,
    get_faulted_vehicles,
    is_ilr_h4_online,
    NORMAL_TEMP_MIN,
    NORMAL_TEMP_MAX,
    FAULT_TARGET_TEMP,
)


def _mock_redis(data: dict | None = None):
    """Create a mock Redis client returning given key/value pairs."""
    store = data or {}
    r = MagicMock()
    r.get = lambda k: store.get(k)
    r.exists = lambda k: k in store
    return r


class TestDeviceInventory:
    def test_device_count(self):
        assert len(DEVICES) == 7

    def test_vehicle_sensors(self):
        vehicle_devs = [d for d in DEVICES if d.kind == "vehicle"]
        assert len(vehicle_devs) == 3
        vids = {d.vehicle_id for d in vehicle_devs}
        assert vids == {"CV-01", "CV-02"}

    def test_ilr_sensors(self):
        ilr_devs = [d for d in DEVICES if d.kind == "ilr"]
        assert len(ilr_devs) == 4
        fids = {d.facility_id for d in ilr_devs}
        assert fids == {"H1", "H2", "H3", "H4"}


class TestNormalTelemetry:
    def test_normal_reading_structure(self):
        dev = Device(device_id="test-01", vehicle_id="CV-99", kind="vehicle")
        r = _mock_redis()
        payload = generate_telemetry(dev, r)
        assert "ts" in payload
        assert "temp_c" in payload
        assert "door_open" in payload
        assert "battery" in payload
        assert payload.get("offline") is None

    def test_normal_temp_range(self):
        dev = Device(device_id="test-01", vehicle_id="CV-99", kind="vehicle")
        r = _mock_redis()
        for _ in range(100):
            payload = generate_telemetry(dev, r)
            assert NORMAL_TEMP_MIN <= payload["temp_c"] <= NORMAL_TEMP_MAX

    def test_battery_decrements(self):
        dev = Device(device_id="test-01", vehicle_id="CV-99", kind="vehicle", battery=95.0)
        r = _mock_redis()
        generate_telemetry(dev, r)
        assert dev.battery < 95.0


class TestFaultMode:
    def test_fault_detection(self):
        faults = [{"device_id": "CV-02", "fault": "compressor_failure", "temp_c": 18.5}]
        r = _mock_redis({"sim:device_faults": json.dumps(faults)})
        result = get_faulted_vehicles(r)
        assert "CV-02" in result

    def test_fault_temp_drift(self):
        dev = Device(device_id="sensor-cv02-a", vehicle_id="CV-02", kind="vehicle")
        faults = [{"device_id": "CV-02", "fault": "compressor_failure"}]
        r = _mock_redis({"sim:device_faults": json.dumps(faults)})

        readings = []
        for _ in range(15):
            payload = generate_telemetry(dev, r)
            readings.append(payload["temp_c"])

        # After 12+ cycles, temp should be near 11°C
        assert readings[-1] > 9.0, f"Expected temp > 9 after ramp, got {readings[-1]}"
        assert readings[0] < readings[-1], "Temperature should increase during fault"

    def test_fault_clears(self):
        dev = Device(device_id="sensor-cv02-a", vehicle_id="CV-02", kind="vehicle")
        faults = [{"device_id": "CV-02", "fault": "compressor_failure"}]
        r_fault = _mock_redis({"sim:device_faults": json.dumps(faults)})

        # Drive into fault
        for _ in range(5):
            generate_telemetry(dev, r_fault)
        assert dev.in_fault is True

        # Clear fault
        r_clear = _mock_redis()
        payload = generate_telemetry(dev, r_clear)
        assert dev.in_fault is False
        assert NORMAL_TEMP_MIN <= payload["temp_c"] <= NORMAL_TEMP_MAX


class TestIlrH4Offline:
    def test_h4_offline_by_default(self):
        dev = Device(device_id="sensor-ilr-h4", facility_id="H4", kind="ilr")
        r = _mock_redis()  # no sim:ilr_h4_online key
        assert is_ilr_h4_online(r) is False
        payload = generate_telemetry(dev, r)
        assert payload["offline"] is True
        assert payload["temp_c"] is None

    def test_h4_online_after_repair(self):
        dev = Device(device_id="sensor-ilr-h4", facility_id="H4", kind="ilr")
        r = _mock_redis({"sim:ilr_h4_online": "1"})
        assert is_ilr_h4_online(r) is True
        payload = generate_telemetry(dev, r)
        assert payload.get("offline") is None
        assert payload["temp_c"] is not None

    def test_other_ilrs_always_online(self):
        for fid in ["H1", "H2", "H3"]:
            dev = Device(device_id=f"sensor-ilr-{fid.lower()}", facility_id=fid, kind="ilr")
            r = _mock_redis()
            payload = generate_telemetry(dev, r)
            assert payload.get("offline") is None
            assert payload["temp_c"] is not None


class TestNoRedis:
    def test_works_with_none_redis(self):
        dev = Device(device_id="sensor-cv01-a", vehicle_id="CV-01", kind="vehicle")
        payload = generate_telemetry(dev, None)
        # With None redis, faulted_vehicles returns empty set, ilr check returns False
        assert payload["temp_c"] is not None

    def test_h4_offline_with_none_redis(self):
        dev = Device(device_id="sensor-ilr-h4", facility_id="H4", kind="ilr")
        payload = generate_telemetry(dev, None)
        assert payload["offline"] is True
