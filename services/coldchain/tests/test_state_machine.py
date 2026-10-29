"""Tests for the cold-chain per-device state machine."""
from __future__ import annotations

from app.state_machine import DeviceState, DeviceStateMachine


def _ts(sec: int) -> str:
    return f"2026-11-01T10:{sec // 60:02d}:{sec % 60:02d}+05:30"


def _make() -> DeviceStateMachine:
    return DeviceStateMachine("sensor-cv02-a", vehicle_id="CV-02")


def test_initial_state():
    m = _make()
    assert m.state == DeviceState.OK
    assert m.last_temp is None


def test_ok_to_warning():
    m = _make()
    events = m.process_reading(_ts(0), 9.0)
    assert m.state == DeviceState.WARNING
    assert events == []  # no alert on WARNING


def test_warning_to_ok():
    m = _make()
    m.process_reading(_ts(0), 9.0)
    assert m.state == DeviceState.WARNING
    m.process_reading(_ts(5), 5.0)
    assert m.state == DeviceState.OK


def test_warning_to_excursion():
    m = _make()
    m.process_reading(_ts(0), 9.0)   # bad 1 → WARNING
    m.process_reading(_ts(5), 9.5)   # bad 2 → still WARNING
    events = m.process_reading(_ts(10), 10.0)  # bad 3 → EXCURSION
    assert m.state == DeviceState.EXCURSION
    assert len(events) == 1
    assert events[0]["type"] == "excursion"
    assert events[0]["severity"] == "critical"
    assert events[0]["vehicle_id"] == "CV-02"


def test_excursion_recovery():
    m = _make()
    for i in range(3):
        m.process_reading(_ts(i * 5), 9.0 + i)
    assert m.state == DeviceState.EXCURSION

    # 5 good readings: still in excursion
    for i in range(5):
        events = m.process_reading(_ts(20 + i * 5), 5.0)
        assert m.state == DeviceState.EXCURSION
        assert events == []

    # 6th good → recovered
    events = m.process_reading(_ts(50), 5.0)
    assert m.state == DeviceState.OK
    assert len(events) == 1
    assert events[0]["type"] == "recovered"
    assert events[0]["severity"] == "resolved"


def test_excursion_reset_on_bad():
    m = _make()
    for i in range(3):
        m.process_reading(_ts(i * 5), 9.0)
    assert m.state == DeviceState.EXCURSION

    # 4 good, then a bad — resets recovery counter
    for i in range(4):
        m.process_reading(_ts(20 + i * 5), 5.0)
    m.process_reading(_ts(45), 12.0)  # bad
    assert m.state == DeviceState.EXCURSION
    assert m.consecutive_good == 0

    # Need full 6 again
    for i in range(6):
        m.process_reading(_ts(50 + i * 5), 5.0)
    assert m.state == DeviceState.OK


def test_door_open_excursion():
    m = _make()
    # Door open for > 2 minutes with good temps
    m.process_reading(_ts(0), 5.0, door_open=True)
    assert m.state == DeviceState.OK
    m.process_reading(_ts(60), 5.0, door_open=True)
    assert m.state == DeviceState.OK
    events = m.process_reading(_ts(125), 5.0, door_open=True)
    assert m.state == DeviceState.EXCURSION
    assert len(events) == 1
    assert events[0]["type"] == "excursion"


def test_door_close_resets():
    m = _make()
    m.process_reading(_ts(0), 5.0, door_open=True)
    m.process_reading(_ts(60), 5.0, door_open=False)  # door closed
    m.process_reading(_ts(125), 5.0, door_open=True)   # new open, timer restarts
    assert m.state == DeviceState.OK


def test_alert_published_once():
    """Alert events only on transitions, not every reading in EXCURSION."""
    m = _make()
    all_events = []
    for i in range(3):
        all_events.extend(m.process_reading(_ts(i * 5), 9.0))
    assert len(all_events) == 1  # only the transition

    # Further bad readings produce no events
    for i in range(5):
        events = m.process_reading(_ts(20 + i * 5), 11.0)
        assert events == []
    assert m.state == DeviceState.EXCURSION


def test_null_temp_is_bad():
    m = _make()
    m.process_reading(_ts(0), None)
    assert m.state == DeviceState.WARNING
    m.process_reading(_ts(5), None)
    events = m.process_reading(_ts(10), None)
    assert m.state == DeviceState.EXCURSION
    assert len(events) == 1


def test_boundary_temps():
    m = _make()
    m.process_reading(_ts(0), 2.0)  # exactly at low boundary → good
    assert m.state == DeviceState.OK
    m.process_reading(_ts(5), 8.0)  # exactly at high boundary → good
    assert m.state == DeviceState.OK
    m.process_reading(_ts(10), 1.99)  # just below → bad
    assert m.state == DeviceState.WARNING


def test_to_status():
    m = _make()
    m.process_reading(_ts(0), 5.0)
    s = m.to_status()
    assert s["device_id"] == "sensor-cv02-a"
    assert s["vehicle_id"] == "CV-02"
    assert s["state"] == "OK"
    assert s["alert"] is False
    assert s["temperature_c"] == 5.0
