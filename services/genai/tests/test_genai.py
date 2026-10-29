"""GenAI gateway tests with FakeProvider — no network calls needed."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app import prompt_registry
from app.cache import LLMCache, make_cache_key
from app.llm_service import LLMService
from app.providers import FakeProvider
from app.validation import make_model, validate_output

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


# ---------- fixtures ----------

@pytest.fixture(autouse=True)
def _load_prompts():
    prompt_registry.load_all(PROMPTS_DIR)


@pytest.fixture
def fake_provider():
    return FakeProvider(responses=[{"reply": "hello from fake"}])


@pytest.fixture
def cache():
    return LLMCache(redis_client=None)


@pytest.fixture
def redis_cache():
    store: dict[str, str] = {}

    class FakeRedis:
        def get(self, key):
            return store.get(key)

        def set(self, key, value, ex=None):
            store[key] = value

    return LLMCache(redis_client=FakeRedis()), store


@pytest.fixture
def service(fake_provider, cache):
    return LLMService(provider=fake_provider, cache=cache)


@pytest.fixture
def service_with_cache(fake_provider, redis_cache):
    cache, _store = redis_cache
    return LLMService(provider=fake_provider, cache=cache), fake_provider


# ---------- prompt registry ----------

def test_prompt_registry_loads():
    refs = prompt_registry.list_prompts()
    assert "smoke@v1" in refs
    assert "extract_stock@v1" in refs


def test_prompt_get():
    spec = prompt_registry.get("smoke", 1)
    assert spec is not None
    assert spec.ref == "smoke@v1"
    assert spec.model == "fast"


def test_prompt_render():
    spec = prompt_registry.get("smoke", 1)
    rendered = spec.render_user({"text": "hello"})
    assert "hello" in rendered


def test_prompt_not_found():
    assert prompt_registry.get("nonexistent", 99) is None


# ---------- validation ----------

def test_validate_output_ok():
    schema = {
        "type": "object",
        "required": ["reply"],
        "properties": {"reply": {"type": "string"}},
    }
    result, err = validate_output({"reply": "hi"}, schema)
    assert err is None
    assert result["reply"] == "hi"


def test_validate_output_missing_field():
    schema = {
        "type": "object",
        "required": ["reply"],
        "properties": {"reply": {"type": "string"}},
    }
    result, err = validate_output({}, schema)
    assert err is not None
    assert result is None


def test_validate_output_not_dict():
    schema = {"type": "object", "properties": {}}
    result, err = validate_output("oops", schema)
    assert err is not None


# ---------- cache ----------

def test_cache_key_deterministic():
    k1 = make_cache_key("smoke", 1, "model-a", {"text": "hi"})
    k2 = make_cache_key("smoke", 1, "model-a", {"text": "hi"})
    assert k1 == k2


def test_cache_key_differs():
    k1 = make_cache_key("smoke", 1, "model-a", {"text": "hi"})
    k2 = make_cache_key("smoke", 1, "model-a", {"text": "bye"})
    assert k1 != k2


def test_cache_miss_no_redis():
    c = LLMCache(redis_client=None)
    assert c.get("anything") is None


def test_cache_roundtrip(redis_cache):
    cache, _store = redis_cache
    cache.set("k1", {"output": {"reply": "cached"}})
    got = cache.get("k1")
    assert got is not None
    assert got["output"]["reply"] == "cached"


# ---------- LLM service: basic complete ----------

def test_complete_smoke(service):
    result = asyncio.get_event_loop().run_until_complete(
        service.complete("test", "smoke", 1, {"text": "hello"})
    )
    assert result["ok"] is True
    assert result["fallback"] is False
    assert result["output"]["reply"] == "hello from fake"
    assert result["prompt_ref"] == "smoke@v1"


def test_complete_unknown_prompt(service):
    result = asyncio.get_event_loop().run_until_complete(
        service.complete("test", "nonexistent", 99, {})
    )
    assert result["ok"] is False
    assert result["fallback"] is True
    assert "not found" in result["error"]


# ---------- cache behaviour ----------

def test_complete_caches_result(service_with_cache):
    svc, provider = service_with_cache
    r1 = asyncio.get_event_loop().run_until_complete(
        svc.complete("test", "smoke", 1, {"text": "cache me"})
    )
    assert r1["ok"] is True
    assert r1["cached"] is False
    assert len(provider.calls) == 1

    r2 = asyncio.get_event_loop().run_until_complete(
        svc.complete("test", "smoke", 1, {"text": "cache me"})
    )
    assert r2["ok"] is True
    assert r2["cached"] is True
    assert len(provider.calls) == 1  # no second call


# ---------- replay mode ----------

def test_replay_miss_returns_fallback(fake_provider, redis_cache):
    cache, _store = redis_cache
    os.environ["DEMO_MODE"] = "replay"
    try:
        from medbal_common.settings import Settings
        s = Settings()
        svc = LLMService(provider=fake_provider, cache=cache)
        result = asyncio.get_event_loop().run_until_complete(
            svc.complete("test", "smoke", 1, {"text": "miss"})
        )
        assert result["fallback"] is True
        assert result["ok"] is False
        assert len(fake_provider.calls) == 0
    finally:
        os.environ["DEMO_MODE"] = "live"


def test_replay_hit_returns_cached(fake_provider, redis_cache):
    cache, _store = redis_cache
    cache.set(
        make_cache_key("smoke", 1, "gemini-3.8-flash", {"text": "hit"}),
        {"output": {"reply": "from cache"}, "confidence": 0.99},
    )
    os.environ["DEMO_MODE"] = "replay"
    try:
        svc = LLMService(provider=fake_provider, cache=cache)
        result = asyncio.get_event_loop().run_until_complete(
            svc.complete("test", "smoke", 1, {"text": "hit"})
        )
        assert result["ok"] is True
        assert result["cached"] is True
        assert result["output"]["reply"] == "from cache"
        assert len(fake_provider.calls) == 0
    finally:
        os.environ["DEMO_MODE"] = "live"


# ---------- retry on validation error ----------

def test_retry_on_invalid_json():
    bad_then_good = FakeProvider(responses=[
        {"wrong_field": "oops"},
        {"wrong_field": "oops again"},
        {"reply": "finally valid"},
    ])
    cache = LLMCache(redis_client=None)
    svc = LLMService(provider=bad_then_good, cache=cache)
    result = asyncio.get_event_loop().run_until_complete(
        svc.complete("test", "smoke", 1, {"text": "retry me"})
    )
    assert result["ok"] is True
    assert result["output"]["reply"] == "finally valid"
    assert len(bad_then_good.calls) == 3


def test_retry_exhausted_returns_fallback():
    always_bad = FakeProvider(responses=[{"wrong_field": "nope"}])
    cache = LLMCache(redis_client=None)
    svc = LLMService(provider=always_bad, cache=cache)
    result = asyncio.get_event_loop().run_until_complete(
        svc.complete("test", "smoke", 1, {"text": "fail me"})
    )
    assert result["ok"] is False
    assert result["fallback"] is True


# ---------- provider interface ----------

def test_fake_provider_records_calls():
    fp = FakeProvider()
    result = fp.complete(
        [{"role": "user", "content": "hi"}],
        model="test-model",
    )
    assert result.output == {"reply": "fake response"}
    assert len(fp.calls) == 1
    assert fp.calls[0]["model"] == "test-model"


# ---------- API endpoint ----------

def test_api_complete():
    from fastapi.testclient import TestClient

    os.environ["LLM_PROVIDER"] = "fake"
    os.environ["DEMO_MODE"] = "live"

    from app.main import create_app
    test_app = create_app()
    client = TestClient(test_app)

    resp = client.post("/llm/complete", json={
        "purpose": "smoke",
        "prompt_id": "smoke",
        "version": 1,
        "input": {"text": "hi"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["prompt_ref"] == "smoke@v1"


def test_api_ai_health():
    from fastapi.testclient import TestClient

    os.environ["LLM_PROVIDER"] = "fake"

    from app.main import create_app
    test_app = create_app()
    client = TestClient(test_app)

    resp = client.get("/ai/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "genai"
    assert "prompts_loaded" in data
    assert data["prompts_loaded"] >= 2
