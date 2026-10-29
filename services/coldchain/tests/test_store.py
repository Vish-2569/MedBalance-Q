"""Tests for in-memory telemetry storage."""
from __future__ import annotations

from app.store import TelemetryStore


def _ts(minute: int) -> str:
    return f"2026-11-01T10:{minute:02d}:00+05:30"


def test_basic_store_and_get():
    s = TelemetryStore()
    stored = s.append("d1", _ts(0), 5.0, False, 95, "OK")
    assert stored is True
    entries = s.get("d1")
    assert len(entries) == 1
    assert entries[0]["temperature_c"] == 5.0


def test_downsampling():
    s = TelemetryStore()
    s.append("d1", _ts(0), 5.0, False, 95, "OK")
    # 30 seconds later → skipped
    stored = s.append("d1", "2026-11-01T10:00:30+05:30", 5.1, False, 95, "OK")
    assert stored is False
    assert len(s.get("d1")) == 1

    # 60 seconds later → stored
    stored = s.append("d1", _ts(1), 5.2, False, 94, "OK")
    assert stored is True
    assert len(s.get("d1")) == 2


def test_since_filter():
    s = TelemetryStore()
    for m in range(5):
        s.append("d1", _ts(m), 5.0, False, 95, "OK")
    entries = s.get("d1", since=_ts(3))
    assert len(entries) == 2  # minute 3 and 4


def test_cap_at_max():
    s = TelemetryStore()
    from datetime import datetime, timedelta, timezone
    tz = timezone(timedelta(hours=5, minutes=30))
    base = datetime(2026, 11, 1, 0, 0, 0, tzinfo=tz)
    for m in range(1500):
        ts = (base + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%S%z")
        # Insert colon in tz offset for fromisoformat compat
        ts = ts[:-2] + ":" + ts[-2:]
        s.append("d1", ts, 5.0, False, 95, "OK")
    assert len(s.get("d1")) == 1440


def test_separate_devices():
    s = TelemetryStore()
    s.append("d1", _ts(0), 5.0, False, 95, "OK")
    s.append("d2", _ts(0), 6.0, False, 90, "OK")
    assert len(s.get("d1")) == 1
    assert len(s.get("d2")) == 1
    assert s.get("d1")[0]["temperature_c"] == 5.0
    assert s.get("d2")[0]["temperature_c"] == 6.0


def test_clear():
    s = TelemetryStore()
    s.append("d1", _ts(0), 5.0, False, 95, "OK")
    s.clear()
    assert s.get("d1") == []
