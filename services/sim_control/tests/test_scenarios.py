"""Scenario endpoint tests."""
from __future__ import annotations

from unittest.mock import patch


def test_list_scenarios(client):
    r = client.get("/scenarios")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 7
    names = {s["name"] for s in data}
    assert "dengue_outbreak" in names
    assert "baseline" in names


def test_activate_scenario(client):
    r = client.post("/scenario/dengue_outbreak")
    assert r.status_code == 200
    assert r.json() == {"activated": "dengue_outbreak"}


def test_unknown_scenario(client):
    r = client.post("/scenario/nonexistent")
    assert r.status_code == 404


def test_signals_after_activation(client):
    client.post("/scenario/dengue_outbreak")
    r = client.get("/signals")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    sig = data[0]
    assert sig["type"] == "outbreak"
    assert sig["facility"] == "H3"


def test_signals_empty_initially(client):
    r = client.get("/signals")
    assert r.status_code == 200
    assert r.json() == []


def test_reset(client):
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.post.return_value = None

        client.post("/scenario/dengue_outbreak")
        r = client.post("/reset?seed=42")
        assert r.status_code == 200
        data = r.json()
        assert data["seed"] == 42
        assert data["sim_date"] == "2026-11-01"

    r = client.get("/signals")
    assert r.json() == []


def test_get_multiplier():
    from app import scenario_defs

    scenario_defs._active.clear()
    scenario_defs.activate("dengue_outbreak")
    assert scenario_defs.get_multiplier("H3", "ORS", 10) == 3.0
    assert scenario_defs.get_multiplier("H3", "ORS", 2) == 1.0
    assert scenario_defs.get_multiplier("H1", "ORS", 10) == 1.0
