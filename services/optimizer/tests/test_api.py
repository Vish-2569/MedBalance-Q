"""API endpoint tests."""
from __future__ import annotations

import os

import pytest


def test_plan_run():
    os.environ["USE_FIXTURES"] = "1"
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.post("/plan/run", json={"mode": "live"})
    assert resp.status_code == 200
    data = resp.json()
    assert "plan" in data
    assert "orders" in data
    assert "metrics" in data
    assert data["plan"]["solver_tier"] in (
        "greedy-f4", "greedy-descent", "neal-sa",
        "qpiai-local", "qpiai-platform", "greedy-f4-fallback", "qubo-empty",
    )
    assert data["plan"]["transfers"] == len(data["orders"])

    for o in data["orders"]:
        assert o["usable"] > 0
        assert o["qty"] > 0


def test_health():
    os.environ["USE_FIXTURES"] = "1"
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
