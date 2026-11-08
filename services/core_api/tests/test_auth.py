"""Tests for authentication and role-based access control."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

svc_path = str(Path(__file__).resolve().parents[1])
if svc_path not in sys.path:
    sys.path.insert(0, svc_path)

from fastapi.testclient import TestClient
from app.main import app

import medbal_common.db as db_mod


@pytest.fixture
def client(db_engine):
    db_mod._engine = db_engine
    db_mod._session_factory = db_mod.get_session_factory(db_engine)
    return TestClient(app, raise_server_exceptions=False)


def test_login_success(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["role"] == "admin"
    assert data["token_type"] == "bearer"


def test_login_bad_password(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/auth/login", json={"username": "nobody", "password": "test"})
    assert r.status_code == 401


def test_me_with_token(client):
    login = client.post("/auth/login", json={"username": "district_officer", "password": "district123"})
    token = login.json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == "district_officer"
    assert data["role"] == "district_officer"


def test_me_without_token(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_approve_requires_auth(client, seed_data):
    r = client.post("/orders/ORD-001/approve")
    assert r.status_code == 401


def test_approve_wrong_role(client, seed_data, auth_headers):
    r = client.post("/orders/ORD-001/approve", headers=auth_headers("pharmacist"))
    assert r.status_code == 403


def test_reject_requires_auth(client, seed_data):
    r = client.post("/orders/ORD-001/reject", json={"reason": "test"})
    assert r.status_code == 401


def test_tamper_requires_admin(client, seed_data, auth_headers):
    r = client.post("/admin/tamper-demo", headers=auth_headers("district_officer"))
    assert r.status_code == 403


def test_tamper_allowed_for_admin(client, seed_data, auth_headers):
    r = client.post("/admin/tamper-demo", headers=auth_headers("admin"))
    assert r.status_code in (200, 404)


def test_users_list(client):
    r = client.get("/auth/users")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 4
    roles = {u["role"] for u in data}
    assert "admin" in roles
    assert "district_officer" in roles
    assert "pharmacist" in roles


def test_custody_scan_requires_auth(client, seed_data):
    r = client.post("/custody/scan", json={"token": "abc", "event": "dispatch"})
    assert r.status_code == 401


def test_custody_scan_wrong_role(client, seed_data, auth_headers):
    r = client.post(
        "/custody/scan",
        json={"token": "abc", "event": "dispatch"},
        headers=auth_headers("operator"),
    )
    assert r.status_code == 403
