from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("DEMO_MODE", "live")
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
