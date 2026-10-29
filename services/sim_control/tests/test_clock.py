"""Clock endpoint tests."""
from __future__ import annotations

import time
from unittest.mock import patch


def test_clock_initial_state(client):
    r = client.get("/clock")
    assert r.status_code == 200
    data = r.json()
    assert data["running"] is False
    assert data["day_index"] == 0
    assert data["sim_date"] == "2026-11-01"
    assert data["date"] == "2026-11-01"
    assert "datetime" in data


def test_clock_start_pause(client):
    r = client.post("/clock/start")
    assert r.status_code == 200
    assert r.json()["running"] is True

    r = client.post("/clock/pause")
    assert r.status_code == 200
    assert r.json()["running"] is False


def test_clock_speed(client):
    r = client.post("/clock/speed", json={"speed": 10})
    assert r.status_code == 200
    assert r.json()["speed"] == 10.0


def test_clock_day_index_advances(client):
    from app.clock_state import clock

    clock.start()
    base = time.monotonic()
    with patch("time.monotonic", return_value=base + 65):
        clock._start_wall = base
        clock.speed = 30.0
        assert clock.day_index == 2
        assert clock.sim_date.isoformat() == "2026-11-03"


def test_clock_pause_preserves_day(client):
    from app.clock_state import clock

    clock._paused_at_day = 0
    clock.speed = 30.0
    base = time.monotonic()
    clock._start_wall = base
    clock.running = True

    with patch("time.monotonic", return_value=base + 65):
        clock.pause()
        assert clock.day_index == 2
        assert clock.running is False

    assert clock.day_index == 2
