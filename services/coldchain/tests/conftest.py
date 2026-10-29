"""Test fixtures for coldchain tests."""
from __future__ import annotations

import os
import sys
from pathlib import Path

libs_path = str(Path(__file__).resolve().parents[3] / "libs" / "medbal_common")
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

svc_path = str(Path(__file__).resolve().parents[1])
if svc_path not in sys.path:
    sys.path.insert(0, svc_path)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("MQTT_URL", "mqtt://localhost:1883")
os.environ.setdefault("USE_FIXTURES", "0")
