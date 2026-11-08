"""Clock endpoint tests."""
from __future__ import annotations

import time
from datetime import date
from unittest.mock import patch


def test_clock_initial_state(client):
    r = client.get("/clock")
    assert r.status_code == 200
    data = r.json()
    assert data["running"] is True
    assert data["speed"] == 1.0
    assert data["sim_date"] == date.today().isoformat()
    assert data["date"] == date.today().isoformat()
    assert "datetime" in data


def test_clock_start_pause(client):
    r = client.post("/clock/pause")
    assert r.status_code == 200
    assert r.json()["running"] is False

    r = client.post("/clock/start")
    assert r.status_code == 200
    assert r.json()["running"] is True


def test_clock_speed(client):
    r = client.post("/clock/speed", json={"speed": 10})
    assert r.status_code == 200
    assert r.json()["speed"] == 10.0


def test_clock_day_index_advances(client):
    from app.clock_state import clock

    clock.set_speed(1.0)
    base = time.monotonic()
    initial_day = clock.day_index
    with patch("time.monotonic", return_value=base + 65):
        clock._start_wall = base - (initial_day * clock._secs_per_day)
        assert clock.day_index == initial_day + 2


def test_clock_pause_preserves_day(client):
    from app.clock_state import clock

    clock.set_speed(1.0)
    base = time.monotonic()
    initial_day = clock.day_index
    clock._start_wall = base - (initial_day * clock._secs_per_day)
    clock.running = True

    with patch("time.monotonic", return_value=base + 65):
        clock.pause()
        assert clock.day_index == initial_day + 2
        assert clock.running is False

    assert clock.day_index == initial_day + 2
