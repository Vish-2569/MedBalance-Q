"""Tests for the copilot agent: tool routing, firewall post-check, SSE streaming."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from app import prompt_registry
from app.cache import LLMCache
from typing import Any

from app.copilot import CopilotSession, _flatten_into, _summarize
from app.copilot_tools import (
    TOOL_DEFINITIONS,
    TOOL_MAP,
    execute_tool,
)
from app.llm_service import LLMService
from app.providers import FakeProvider, LLMResult

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


@pytest.fixture(autouse=True)
def _load_prompts():
    prompt_registry.load_all(PROMPTS_DIR)


@pytest.fixture(autouse=True)
def _use_fixtures():
    old = os.environ.get("USE_FIXTURES")
    os.environ["USE_FIXTURES"] = "1"
    yield
    if old is None:
        os.environ.pop("USE_FIXTURES", None)
    else:
        os.environ["USE_FIXTURES"] = old


# ── Tool definitions ──────────────────────────────────────────────

def test_tool_definitions_complete():
    names = {t["name"] for t in TOOL_DEFINITIONS}
    expected = {
        "get_district_overview", "get_stock_position", "explain_order",
        "why_not", "what_if", "get_coldchain_status",
        "get_audit_trail", "compare_policies",
    }
    assert names == expected


def test_tool_definitions_have_schemas():
    for t in TOOL_DEFINITIONS:
        assert "name" in t
        assert "description" in t
        assert "parameters" in t
        assert t["parameters"]["type"] == "object"


def test_all_tools_in_map():
    for t in TOOL_DEFINITIONS:
        assert t["name"] in TOOL_MAP


# ── Tool execution (fixture mode) ────────────────────────────────

def test_tool_district_overview():
    result = asyncio.get_event_loop().run_until_complete(
        execute_tool("get_district_overview", {})
    )
    assert "facilities" in result
    assert len(result["facilities"]) >= 3
    assert "total_shortage" in result


def test_tool_stock_position():
    result = asyncio.get_event_loop().run_until_complete(
        execute_tool("get_stock_position", {"facility": "H1", "drug": "INSUL"})
    )
    assert "effective_stock" in result
    assert "shortage" in result


def test_tool_stock_position_not_found():
    result = asyncio.get_event_loop().run_until_complete(
        execute_tool("get_stock_position", {"facility": "H99", "drug": "FAKE"})
    )
    assert "error" in result


def test_tool_explain_order():
    result = asyncio.get_event_loop().run_until_complete(
        execute_tool("explain_order", {"order_id": "ORD-001"})
    )
    assert "order" in result
    assert result["order"]["id"] == "ORD-001"
    assert result["order"]["dta_number"].startswith("DTA/")


def test_tool_why_not_h4_insulin():
    result = asyncio.get_event_loop().run_until_complete(
        execute_tool("why_not", {"facility": "H4", "drug": "INSUL"})
    )
    assert "candidates" in result
    assert len(result["candidates"]) >= 1
    rules = result["candidates"][0].get("failed_rules", [])
    assert any("F3" in r for r in rules)


def test_tool_what_if_repair():
    result = asyncio.get_event_loop().run_until_complete(
        execute_tool("what_if", {
            "overrides": [{"action": "repair_cold_storage", "facility": "H4"}]
        })
    )
    assert "diff" in result
    added = result["diff"].get("orders_added", [])
    assert len(added) >= 1
    assert added[0]["drug_code"] == "INSUL"


def test_tool_coldchain_status():
    result = asyncio.get_event_loop().run_until_complete(
        execute_tool("get_coldchain_status", {})
    )
    assert "devices" in result
    assert len(result["devices"]) >= 1


def test_tool_audit_trail():
    result = asyncio.get_event_loop().run_until_complete(
        execute_tool("get_audit_trail", {"order_id": "ORD-005"})
    )
    assert "entries" in result
    assert len(result["entries"]) >= 1


def test_tool_compare_policies():
    result = asyncio.get_event_loop().run_until_complete(
        execute_tool("compare_policies", {})
    )
    assert "policies" in result
    assert len(result["policies"]) >= 3


def test_tool_unknown():
    result = asyncio.get_event_loop().run_until_complete(
        execute_tool("nonexistent_tool", {})
    )
    assert "error" in result


# ── Copilot agent (FakeProvider, no tool calls) ───────────────────

def test_copilot_basic_response():
    provider = FakeProvider(responses=[{
        "text": "The district has 5 facilities with a total shortage of 393 units."
    }])
    cache = LLMCache(redis_client=None)
    svc = LLMService(provider=provider, cache=cache)
    session = CopilotSession(svc)

    events = []
    async def collect():
        async for e in session.chat(None, "Give me an overview"):
            events.append(e)

    asyncio.get_event_loop().run_until_complete(collect())

    types = [e["type"] for e in events]
    assert "session" in types
    assert "answer" in types or "token" in types
    answer_evt = next((e for e in events if e["type"] == "answer"), None)
    if answer_evt:
        assert "text" in answer_evt


def test_copilot_creates_session_id():
    provider = FakeProvider(responses=[{"text": "Hello"}])
    cache = LLMCache(redis_client=None)
    svc = LLMService(provider=provider, cache=cache)
    session = CopilotSession(svc)

    events = []
    async def collect():
        async for e in session.chat(None, "Hi"):
            events.append(e)

    asyncio.get_event_loop().run_until_complete(collect())

    session_evt = next(e for e in events if e["type"] == "session")
    assert session_evt["session_id"].startswith("cs-")


def test_copilot_resumes_session():
    provider = FakeProvider(responses=[{"text": "First"}, {"text": "Second"}])
    cache = LLMCache(redis_client=None)
    svc = LLMService(provider=provider, cache=cache)
    session = CopilotSession(svc)

    events1 = []
    async def collect1():
        async for e in session.chat(None, "First message"):
            events1.append(e)

    asyncio.get_event_loop().run_until_complete(collect1())
    sid = next(e for e in events1 if e["type"] == "session")["session_id"]

    events2 = []
    async def collect2():
        async for e in session.chat(sid, "Second message"):
            events2.append(e)

    asyncio.get_event_loop().run_until_complete(collect2())
    sid2 = next(e for e in events2 if e["type"] == "session")["session_id"]
    assert sid2 == sid


# ── Copilot with simulated tool calls ─────────────────────────────

class ToolCallingProvider(FakeProvider):
    """Provider that returns tool_calls on first call, then a text answer."""

    def __init__(self, tool_name: str, tool_args: dict, final_text: str):
        super().__init__()
        self._tool_name = tool_name
        self._tool_args = tool_args
        self._final_text = final_text
        self._round = 0

    def complete(self, messages, **kwargs) -> LLMResult:
        self.calls.append({"messages": messages, **kwargs})
        self._round += 1
        if self._round == 1:
            return LLMResult(
                output={"text": ""},
                model=kwargs.get("model", "fake"),
                confidence=1.0,
                tokens_in=10,
                tokens_out=5,
                tool_calls=[{"name": self._tool_name, "args": self._tool_args}],
            )
        return LLMResult(
            output={"text": self._final_text},
            model=kwargs.get("model", "fake"),
            confidence=1.0,
            tokens_in=10,
            tokens_out=20,
        )


def test_copilot_calls_why_not_tool():
    provider = ToolCallingProvider(
        "why_not",
        {"facility": "H4", "drug": "INSUL"},
        "H4 (SIM-Primary Health Centre) did not receive insulin because it has no cold storage (F3). "
        "The only source lot at W0 has 50 vials but the F3 cold chain rule blocks the transfer.",
    )
    cache = LLMCache(redis_client=None)
    svc = LLMService(provider=provider, cache=cache)
    session = CopilotSession(svc)

    events = []
    async def collect():
        async for e in session.chat(None, "Why didn't Hesaraghatta get insulin?"):
            events.append(e)

    asyncio.get_event_loop().run_until_complete(collect())

    types = [e["type"] for e in events]
    assert "tool_call" in types
    assert "tool_result" in types

    tc = next(e for e in events if e["type"] == "tool_call")
    assert tc["name"] == "why_not"
    assert tc["args"]["facility"] == "H4"

    tr = next(e for e in events if e["type"] == "tool_result")
    assert "F3" in tr["summary"] or "candidate" in tr["summary"]

    answer = next(e for e in events if e["type"] == "answer")
    assert "F3" in answer["text"] or "cold" in answer["text"].lower()


def test_copilot_calls_what_if_tool():
    provider = ToolCallingProvider(
        "what_if",
        {"overrides": [{"action": "repair_cold_storage", "facility": "H4"}]},
        "Repairing H4's fridge would enable 28 vials of insulin to be transferred, "
        "improving shortage reduction by 0.13 and adding 1 additional trip at ₹170 extra cost.",
    )
    cache = LLMCache(redis_client=None)
    svc = LLMService(provider=provider, cache=cache)
    session = CopilotSession(svc)

    events = []
    async def collect():
        async for e in session.chat(None, "What if we repair its fridge?"):
            events.append(e)

    asyncio.get_event_loop().run_until_complete(collect())

    tc = next(e for e in events if e["type"] == "tool_call")
    assert tc["name"] == "what_if"

    answer = next(e for e in events if e["type"] == "answer")
    assert "28" in answer["text"] or "insulin" in answer["text"].lower()


def test_copilot_firewall_blocks_bad_number():
    provider = ToolCallingProvider(
        "get_stock_position",
        {"facility": "H1", "drug": "INSUL"},
        "H1 has 99999 vials of insulin in stock with a shortage of 8.",
    )
    cache = LLMCache(redis_client=None)
    svc = LLMService(provider=provider, cache=cache)
    session = CopilotSession(svc)

    events = []
    async def collect():
        async for e in session.chat(None, "How much insulin at H1?"):
            events.append(e)

    asyncio.get_event_loop().run_until_complete(collect())

    answer = next(e for e in events if e["type"] == "answer")
    assert answer["grounding_ok"] is False
    assert "could not be verified" in answer["text"]


# ── Helper functions ──────────────────────────────────────────────

def test_flatten_into():
    facts: dict[str, Any] = {}
    _flatten_into({"a": 1, "b": {"c": 2}, "d": [3, 4]}, facts)
    assert facts["a"] == 1
    assert facts["b.c"] == 2


def test_summarize_functions():
    s1 = _summarize("get_district_overview", {"facilities": [1, 2], "total_shortage": 5})
    assert "2" in s1  # 2 facilities
    s2 = _summarize("get_stock_position", {"shortage": 10, "effective_stock": 100})
    assert "10" in s2
    s3 = _summarize("why_not", {"error": "fail"})
    assert "fail" in s3


# ── API endpoint ──────────────────────────────────────────────────

def test_api_copilot_chat():
    from fastapi.testclient import TestClient

    os.environ["LLM_PROVIDER"] = "fake"
    os.environ["DEMO_MODE"] = "live"

    from app.main import create_app
    test_app = create_app()
    client = TestClient(test_app)

    resp = client.post("/copilot/chat", json={
        "message": "Hello, what's the stock situation?",
    })
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    lines = resp.text.strip().split("\n")
    data_lines = [l for l in lines if l.startswith("data: ") and l != "data: [DONE]"]
    assert len(data_lines) >= 2

    first = json.loads(data_lines[0].removeprefix("data: "))
    assert first["type"] == "session"
    assert first["session_id"].startswith("cs-")


# ── Golden eval structure ─────────────────────────────────────────

def test_golden_evals_structure():
    evals_path = Path(__file__).resolve().parents[3] / "evals" / "golden" / "copilot.json"
    assert evals_path.exists()
    data = json.loads(evals_path.read_text(encoding="utf-8"))
    assert "questions" in data
    assert len(data["questions"]) == 12
    for q in data["questions"]:
        assert "id" in q
        assert "question" in q
        assert "expected_tools" in q
        assert "language" in q


# ── Prompt loaded ─────────────────────────────────────────────────

def test_copilot_prompt_loaded():
    spec = prompt_registry.get("copilot", 1)
    assert spec is not None
    assert spec.model == "smart"
    assert "District Drug Officer" in spec.system
    assert "tool result" in spec.system
    assert "Form 19" not in spec.system
