"""Copilot agent: streaming tool-using chat for the District Drug Officer.

Up to 5 tool-call rounds per turn. Final answer post-checked with the
P15 numeric firewall against concatenated tool results.
Read-only — never approves or changes live data.
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any, AsyncIterator

from medbal_common.logging import get_logger
from medbal_common.settings import settings

from . import prompt_registry
from .copilot_tools import TOOL_DEFINITIONS, execute_tool
from .firewall import check_narration

log = get_logger("genai.copilot")

MAX_TOOL_ROUNDS = 5


class CopilotSession:
    def __init__(self, llm_service: Any, db_engine: Any | None = None):
        self._llm = llm_service
        self._engine = db_engine

    async def chat(
        self,
        session_id: str | None,
        message: str,
        user_id: str = "demo",
    ) -> AsyncIterator[dict[str, Any]]:
        if not session_id:
            session_id = f"cs-{uuid.uuid4().hex[:12]}"
            self._create_session(session_id, user_id)
        yield {"type": "session", "session_id": session_id}

        history = self._load_history(session_id)

        spec = prompt_registry.get("copilot", 1)
        system_prompt = spec.system if spec else _FALLBACK_SYSTEM

        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        self._save_message(session_id, "user", message)

        all_tool_facts: dict[str, Any] = {}
        tool_calls_log: list[dict[str, Any]] = []
        final_text = ""

        for round_idx in range(MAX_TOOL_ROUNDS + 1):
            result = await self._call_llm(messages, spec)
            if not result or result.get("error"):
                error = result.get("error") if result else "The AI provider could not generate a response."
                fallback_tool = _demo_tool_for_message(message)
                if fallback_tool:
                    name, args = fallback_tool
                    yield {"type": "tool_call", "name": name, "args": args}
                    tool_result = await execute_tool(name, args)
                    if _tool_result_is_empty(name, tool_result):
                        fixture_result = await execute_tool(name, args, use_fixtures=True)
                        if not _tool_result_is_empty(name, fixture_result):
                            tool_result = {
                                **fixture_result,
                                "_data_source": "illustrative_demo_fixture",
                            }
                    yield {
                        "type": "tool_result",
                        "name": name,
                        "summary": _summarize(name, tool_result),
                        "result": tool_result,
                    }
                    tool_calls_log.append({
                        "name": name, "args": args, "result": tool_result,
                    })
                    _flatten_into(tool_result, all_tool_facts)
                    final_text = _format_demo_response(name, tool_result, error)
                else:
                    final_text = (
                        f"Demo fallback: the live AI provider is unavailable ({error}). "
                        "I couldn't select a data lookup for this question. Try asking "
                        "about district stock, a facility and drug, an order ID, "
                        "cold-chain status, or facility policies."
                    )
                log.warning("copilot_demo_fallback", provider_error=error)
                break

            tool_calls = result.get("tool_calls") or []
            output = result.get("output", {})
            text = _extract_text(output)

            if not tool_calls or round_idx >= MAX_TOOL_ROUNDS:
                final_text = text
                yield {"type": "token", "text": final_text}
                break

            messages.append({"role": "assistant", "content": text or "Calling tools…"})

            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("args", {})
                yield {"type": "tool_call", "name": name, "args": args}

                tool_result = await execute_tool(name, args)
                _flatten_into(tool_result, all_tool_facts)
                tool_calls_log.append({"name": name, "args": args, "result": tool_result})

                summary = _summarize(name, tool_result)
                yield {
                    "type": "tool_result",
                    "name": name,
                    "summary": summary,
                    "result": tool_result,
                }

                messages.append({
                    "role": "user",
                    "content": f"[Tool result — {name}]\n{json.dumps(tool_result, default=str)}",
                })

        grounding_ok = True
        if final_text and all_tool_facts:
            fw = check_narration(final_text, all_tool_facts)
            grounding_ok = fw["grounding_ok"]
            if not grounding_ok:
                final_text += "\n\n⚠ Some figures could not be verified against tool results."
                log.warning("copilot_firewall_block",
                            session=session_id,
                            mismatches=len(fw.get("mismatches", [])))

        self._save_message(session_id, "assistant", final_text,
                           tool_calls=tool_calls_log or None)

        yield {"type": "answer", "text": final_text, "grounding_ok": grounding_ok}

    # ── LLM call ──────────────────────────────────────────────────

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        spec: Any | None,
    ) -> dict[str, Any] | None:
        try:
            provider = self._llm._provider
            model = self._llm._resolve_model(spec.model if spec else "smart")
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: provider.complete(
                        messages,
                        tools=TOOL_DEFINITIONS,
                        model=model,
                        temperature=spec.temperature if spec else 0.0,
                        max_tokens=spec.max_tokens if spec else 2048,
                        timeout=45.0,
                    ),
                ),
                timeout=50.0,
            )
            resp: dict[str, Any] = {"output": result.output, "model": model}
            if result.tool_calls:
                resp["tool_calls"] = result.tool_calls
            return resp
        except Exception as exc:
            error = str(exc)
            log.warning("copilot_llm_error", error=error)
            if "resource_exhausted" in error.lower() or "429" in error:
                message = (
                    "The Gemini API quota is exhausted. Check the configured "
                    "project's quota or billing, then try again."
                )
            else:
                message = "The AI provider could not generate a response. Check the GenAI service logs."
            return {"error": message}

    # ── DB persistence ────────────────────────────────────────────

    def _create_session(self, session_id: str, user_id: str) -> None:
        if not self._engine:
            return
        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                conn.execute(
                    text("INSERT INTO chat_session (id, user_id) "
                         "VALUES (:id, :uid) ON CONFLICT DO NOTHING"),
                    {"id": session_id, "uid": user_id},
                )
                conn.commit()
        except Exception as exc:
            log.warning("create_session_failed", error=str(exc))

    def _load_history(self, session_id: str) -> list[dict[str, Any]]:
        if not self._engine:
            return []
        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT role, content, tool_calls FROM chat_message "
                         "WHERE session_id = :sid ORDER BY id"),
                    {"sid": session_id},
                ).mappings().all()
            out: list[dict[str, Any]] = []
            for r in rows:
                msg: dict[str, Any] = {"role": r["role"], "content": r["content"]}
                tc = r["tool_calls"]
                if tc:
                    msg["tool_calls"] = json.loads(tc) if isinstance(tc, str) else tc
                out.append(msg)
            return out
        except Exception as exc:
            log.warning("load_history_failed", error=str(exc))
            return []

    def _save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        if not self._engine:
            return
        try:
            from sqlalchemy import text
            tc_json = json.dumps(tool_calls, default=str) if tool_calls else None
            with self._engine.connect() as conn:
                conn.execute(
                    text("INSERT INTO chat_message "
                         "(session_id, role, content, tool_calls) "
                         "VALUES (:sid, :role, :content, CAST(:tc AS jsonb))"),
                    {"sid": session_id, "role": role,
                     "content": content, "tc": tc_json},
                )
                conn.commit()
        except Exception as exc:
            log.warning("save_message_failed", error=str(exc))


# ── Helpers ───────────────────────────────────────────────────────

_FALLBACK_SYSTEM = (
    "You are the MedBalance-Q copilot, an assistant to the District Drug "
    "Officer. Every number must come from a tool result. Say 'I don't have "
    "that information' instead of guessing."
)


def _demo_tool_for_message(message: str) -> tuple[str, dict[str, Any]] | None:
    """Choose a read-only data tool for a transparent provider-outage fallback."""
    text = message.lower()
    facility_match = re.search(r"(?<![a-z0-9])(?:h[1-4]|w0)(?![a-z0-9])", text)
    facility = facility_match.group(0).upper() if facility_match else None
    if not facility and "hesaraghatta" in text:
        facility = "H3"

    drug = None
    for terms, code in (
        (("insulin", "insul", "ಇನ್ಸುಲಿನ್"), "INSUL"),
        (("paracetamol", "para500", "para 500"), "PARA500"),
        (("amoxicillin", "amox500", "amox 500"), "AMOX500"),
        (("ors",), "ORS"),
    ):
        if any(term in text for term in terms):
            drug = code
            break

    order_match = re.search(r"\bord[- ]?\d{3}\b", text, re.IGNORECASE)
    if order_match:
        order_id = order_match.group(0).upper().replace(" ", "-")
        if "audit" in text or "trail" in text:
            return "get_audit_trail", {"order_id": order_id}
        return "explain_order", {"order_id": order_id}
    if "cold chain" in text or "cold-chain" in text or "ಶೀತ" in text:
        return "get_coldchain_status", {}
    if "polic" in text:
        return "compare_policies", {}
    if ("why" in text or "ಏಕೆ" in text) and facility and drug:
        return "why_not", {"facility": facility, "drug": drug}
    if ("what if" in text or "what-if" in text) and "repair" in text and facility == "H4":
        return "what_if", {
            "overrides": [{"action": "repair_cold_storage", "facility": facility}],
        }
    if ("what if" in text or "what-if" in text) and "close" in text:
        route = re.search(
            r"\b(w0|h[1-4])\s+(?:to|->)\s+(w0|h[1-4])\b",
            text,
            re.IGNORECASE,
        )
        if route:
            return "what_if", {
                "overrides": [{
                    "action": "close_route",
                    "src": route.group(1).upper(),
                    "dst": route.group(2).upper(),
                }],
            }
    if facility and drug and any(term in text for term in ("stock", "position", "have", "how much")):
        return "get_stock_position", {"facility": facility, "drug": drug}
    if any(term in text for term in ("district", "overall", "overview", "stock situation")):
        return "get_district_overview", {}
    return None


def _format_demo_response(name: str, result: dict[str, Any], provider_error: str) -> str:
    if result.get("_data_source") == "illustrative_demo_fixture":
        prefix = (
            "Demo fallback: live AI and live lookup data are unavailable; "
            "the following is illustrative fixture data. "
        )
    else:
        prefix = f"Demo fallback (live AI unavailable: {provider_error}). "
    if result.get("error"):
        return prefix + f"I couldn't retrieve supporting data: {result['error']}"

    if name == "get_district_overview":
        return (
            prefix
            + f"District stock data reports total shortage {result.get('total_shortage', 'not available')} "
            + f"and at-risk quantity {result.get('total_at_risk', 'not available')}. "
            + f"Facilities: {', '.join(f.get('id', '') for f in result.get('facilities', [])) or 'none returned'}."
        )
    if name == "get_stock_position":
        return (
            prefix
            + f"{result.get('facility_id', 'Facility')} / {result.get('drug_code', 'drug')}: "
            + f"effective stock {result.get('effective_stock', 'not available')}, "
            + f"shortage {result.get('shortage', 'not available')}, "
            + f"at risk {result.get('at_risk', 'not available')}, "
            + f"reserve {result.get('reserve', 'not available')}."
        )
    if name == "why_not":
        reasons = [
            reason
            for candidate in result.get("candidates", [])
            for reason in candidate.get("failed_rules", [])
        ]
        detail = " ".join(reasons) if reasons else "No blocking candidate rule was returned."
        return prefix + f"{result.get('facility_id', 'Facility')} / {result.get('drug_code', 'drug')}: {detail}"
    if name == "explain_order":
        order = result.get("order", {})
        if not order:
            return prefix + "No order details were returned."
        return (
            prefix
            + f"Order {order.get('id', '')} is {order.get('qty', 'not available')} "
            + f"{order.get('drug_name', order.get('drug_code', 'units'))} from "
            + f"{order.get('src_facility_id', 'unknown source')} to "
            + f"{order.get('dst_facility_id', 'unknown destination')}; "
            + f"status: {order.get('status', 'not available')}."
        )
    if name == "get_audit_trail":
        entries = result.get("entries", [])
        details = "; ".join(
            f"{entry.get('actor', 'unknown actor')}: {entry.get('action', 'recorded action')}"
            for entry in entries
        )
        return prefix + (f"Audit trail for {result.get('order_id', 'the order')}: {details}." if details else "No audit entries were returned.")
    if name == "get_coldchain_status":
        devices = result.get("devices", [])
        details = "; ".join(
            f"{device.get('device_id', 'device')} is {device.get('state', 'unknown')} "
            f"at {device.get('temperature_c', 'unknown')} C"
            for device in devices
        )
        return prefix + (f"Cold-chain readings: {details}." if details else "No cold-chain device readings were returned.")
    if name == "compare_policies":
        details = "; ".join(
            f"{policy.get('facility_id', '?')} / {policy.get('drug_code', '?')}: "
            f"minimum reserve {policy.get('min_reserve_days', 'not available')} days, "
            f"target {policy.get('target_days', 'not available')} days"
            for policy in result.get("policies", [])
        )
        return prefix + (f"Policy data: {details}." if details else "No policy records were returned.")
    if name == "what_if":
        diff = result.get("diff", {})
        additions = diff.get("orders_added", [])
        details = "; ".join(
            f"{order.get('qty', 'not available')} {order.get('drug_code', 'units')} to "
            f"{order.get('dst_facility_id', 'unknown facility')}"
            for order in additions
        )
        return (
            prefix
            + f"The scenario reports shortage-reduction change "
            + f"{diff.get('shortage_reduction_delta', 'not available')}; "
            + f"proposed additions: {details or 'none returned'}."
        )
    return prefix + "The data tool returned a result, but it has no demo summary."


def _tool_result_is_empty(name: str, result: dict[str, Any]) -> bool:
    if result.get("error"):
        return True
    if name == "get_district_overview":
        return not result.get("facilities")
    if name == "get_stock_position":
        return "effective_stock" not in result and "shortage" not in result
    if name == "explain_order":
        return not result.get("order")
    if name == "why_not":
        return not result.get("candidates")
    if name == "get_coldchain_status":
        return not result.get("devices")
    if name == "get_audit_trail":
        return not result.get("entries")
    if name == "compare_policies":
        return not result.get("policies")
    if name == "what_if":
        return not result.get("baseline") and not result.get("scenario")
    return False


def _extract_text(output: Any) -> str:
    if isinstance(output, dict):
        return output.get("text", output.get("reply", ""))
    if isinstance(output, str):
        return output
    return str(output) if output else ""


def _flatten_into(data: Any, facts: dict[str, Any], prefix: str = "") -> None:
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}{k}" if prefix else k
            if isinstance(v, dict):
                _flatten_into(v, facts, f"{key}.")
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    _flatten_into(item, facts, f"{key}.{i}.")
            else:
                facts[key] = v
    elif isinstance(data, (int, float, str)):
        if prefix:
            facts[prefix.rstrip(".")] = data


def _summarize(name: str, result: dict[str, Any]) -> str:
    if "error" in result:
        return f"{name}: {result['error']}"
    if name == "get_district_overview":
        return f"District: {len(result.get('facilities', []))} facilities, shortage={result.get('total_shortage', '?')}"
    if name == "get_stock_position":
        return f"Position: shortage={result.get('shortage', 0)}, effective={result.get('effective_stock', '?')}"
    if name == "explain_order":
        o = result.get("order", {})
        return f"Order {o.get('id','?')}: {o.get('drug_name','?')} {o.get('qty','?')} → {o.get('dst_facility_id','?')}, status={o.get('status','?')}"
    if name == "why_not":
        n = len(result.get("candidates", []))
        return f"Why-not: {n} candidate(s) evaluated"
    if name == "what_if":
        d = result.get("diff", {})
        return f"What-if: shortage Δ={d.get('shortage_reduction_delta', '?')}, +{len(d.get('orders_added', []))} orders"
    if name == "get_coldchain_status":
        return f"Cold chain: {len(result.get('devices', []))} devices"
    if name == "get_audit_trail":
        return f"Audit: {len(result.get('entries', []))} entries"
    if name == "compare_policies":
        return f"Policies: {len(result.get('policies', []))} entries"
    return f"{name}: done"
