"""Narration service: per-order grounded narrations and credit memos.

Calls the LLM via the existing LLMService, then runs through the numeric
firewall. Deterministic fallback if the LLM is unavailable or the firewall
blocks.
"""
from __future__ import annotations

from typing import Any

from medbal_common.logging import get_logger

from .firewall import check_narration, _deterministic_narration

log = get_logger("genai.narration")


async def narrate_order(
    llm_service: Any,
    order_facts: dict[str, Any],
) -> dict[str, Any]:
    """Generate a grounded narration for a single order.

    Returns:
        {
            "narration": str,
            "grounding_ok": bool,
            "model": str,
            "prompt_ref": str,
            "firewall": {...},
            "fallback": bool,
        }
    """
    result = await llm_service.complete(
        purpose="narrate",
        prompt_id="narrate",
        version=1,
        input_data=order_facts,
    )

    if not result.get("ok") or not result.get("output"):
        narration = _deterministic_narration(order_facts)
        return {
            "narration": narration,
            "grounding_ok": True,
            "model": result.get("model", ""),
            "prompt_ref": result.get("prompt_ref", "narrate@v1"),
            "firewall": {"grounding_ok": True, "mismatches": [], "source": "deterministic"},
            "fallback": True,
        }

    raw_narration = result["output"].get("narration", "")
    if not raw_narration:
        narration = _deterministic_narration(order_facts)
        return {
            "narration": narration,
            "grounding_ok": True,
            "model": result.get("model", ""),
            "prompt_ref": result.get("prompt_ref", "narrate@v1"),
            "firewall": {"grounding_ok": True, "mismatches": [], "source": "deterministic"},
            "fallback": True,
        }

    fw = check_narration(raw_narration, order_facts)

    return {
        "narration": fw["narration"],
        "grounding_ok": fw["grounding_ok"],
        "model": result.get("model", ""),
        "prompt_ref": result.get("prompt_ref", "narrate@v1"),
        "firewall": fw,
        "fallback": False,
    }


async def narrate_credit_memo(
    llm_service: Any,
    memo_facts: dict[str, Any],
) -> dict[str, Any]:
    """Generate a grounded credit memo paragraph."""
    result = await llm_service.complete(
        purpose="credit_memo",
        prompt_id="credit_memo",
        version=1,
        input_data=memo_facts,
    )

    if not result.get("ok") or not result.get("output"):
        paragraph = _deterministic_credit_memo(memo_facts)
        return {
            "paragraph": paragraph,
            "grounding_ok": True,
            "fallback": True,
            "firewall": {"grounding_ok": True, "source": "deterministic"},
        }

    raw_paragraph = result["output"].get("paragraph", "")
    if not raw_paragraph:
        paragraph = _deterministic_credit_memo(memo_facts)
        return {
            "paragraph": paragraph,
            "grounding_ok": True,
            "fallback": True,
            "firewall": {"grounding_ok": True, "source": "deterministic"},
        }

    fw = check_narration(raw_paragraph, memo_facts)

    return {
        "paragraph": fw["narration"],
        "grounding_ok": fw["grounding_ok"],
        "firewall": fw,
        "fallback": False,
    }


def _deterministic_credit_memo(facts: dict[str, Any]) -> str:
    donor = facts.get("donor_facility", facts.get("donor_facility_id", "the facility"))
    units = facts.get("total_units", "?")
    value = facts.get("value_inr", "?")
    drugs = facts.get("drugs_summary", "medicines")
    receivers = facts.get("receivers", "receiving facilities")

    return (
        f"This memo acknowledges {donor}'s contribution of {units} units of {drugs} "
        f"valued at ₹{value}, redistributed to {receivers} before expiry. "
        f"A credit of ₹{value} is recommended against {donor}'s next indent."
    )
