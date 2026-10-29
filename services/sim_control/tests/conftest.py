from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

libs_path = str(Path(__file__).resolve().parents[3] / "libs" / "medbal_common")
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

os.environ.setdefault("USE_FIXTURES", "0")
os.environ.setdefault("SIM_START_DATE", "2026-11-01")
os.environ.setdefault("SIM_DAY_SECONDS", "30")
os.environ.setdefault("SIM_SEED", "42")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import medbal_common.bus  # noqa: E402 — force module into namespace before patching

_fake_redis = MagicMock()
_fake_redis.get.return_value = None
_fake_redis.xadd.return_value = "1-0"


@pytest.fixture(autouse=True)
def _mock_redis():
    with patch.object(medbal_common.bus, "get_redis", return_value=_fake_redis):
        with patch.object(medbal_common.bus, "publish", return_value="1-0"):
            yield
    _fake_redis.reset_mock()


@pytest.fixture(autouse=True)
def _reset_state():
    from app.clock_state import clock
    from app.scenario_defs import _active

    clock.reset()
    _active.clear()
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    return TestClient(app, raise_server_exceptions=False)
