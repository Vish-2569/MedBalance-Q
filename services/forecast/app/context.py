"""LLM context multiplier with guardrails.

Fetches signals from sim-control, calls genai gateway for relevant
facility×drug pairs, clamps and validates the result.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import httpx

from medbal_common.logging import get_logger
from medbal_common.settings import settings

log = get_logger("forecast.context")

GENAI_URL = "http://genai:8003"
SIM_CONTROL_URL = "http://sim-control:8100"

MULTIPLIER_MIN = 0.5
MULTIPLIER_MAX = 3.0
CONFIDENCE_THRESHOLD = 0.5

SEASONAL_CALENDAR: list[dict[str, Any]] = [
    {"id": "season_monsoon", "type": "monsoon", "months": [6, 7, 8, 9],
     "params": {"affects": ["ORS", "AMOX500", "AMOX"], "factor": 1.3},
     "fired_at": "seasonal"},
    {"id": "season_winter", "type": "winter", "months": [11, 12, 1, 2],
     "params": {"affects": ["PARA500", "PCM", "AMOX500", "AMOX"], "factor": 1.15},
     "fired_at": "seasonal"},
    {"id": "season_dengue", "type": "dengue_season", "months": [9, 10, 11],
     "params": {"affects": ["ORS", "PCM", "PARA500"], "factor": 1.2},
     "fired_at": "seasonal"},
    {"id": "festival_dasara", "type": "festival", "months": [10],
     "params": {"affects": [], "factor": 0.85},
     "fired_at": "seasonal"},
]


@dataclass
class ContextResult:
    multiplier: float
    confidence: float
    signal_ids: list[str]
    reasoning: str
    method: str  # "llm" | "no_signal" | "guardrail_fallback"


def fetch_signals(today=None) -> list[dict[str, Any]]:
    """Fetch active signals from sim-control + seasonal calendar."""
    sim_signals: list[dict[str, Any]] = []

    try:
        if settings.USE_FIXTURES:
            sim_signals = []
        else:
            resp = httpx.get(f"{SIM_CONTROL_URL}/signals", timeout=5.0)
            resp.raise_for_status()
            raw = resp.json()
            for i, s in enumerate(raw):
                if "id" not in s:
                    s["id"] = f"sig_{s.get('type', 'unknown')}_{i}"
                sim_signals.append(s)
    except Exception as e:
        log.warning("signals_fetch_failed", error=str(e))

    if today:
        month = today.month
        for cal in SEASONAL_CALENDAR:
            if month in cal["months"]:
                sim_signals.append(cal)

    return sim_signals


def relevant_signals(
    facility_id: str,
    drug_code: str,
    signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter signals relevant to this facility×drug pair."""
    relevant = []
    for s in signals:
        params = s.get("params", {})

        # Outbreak/campaign targeting specific facility+drug
        sig_fac = params.get("facility_id")
        sig_drug = params.get("drug_code")
        if sig_fac and sig_fac != facility_id:
            continue
        if sig_drug and sig_drug != drug_code:
            continue

        # Seasonal: check if drug is in affects list
        affects = params.get("affects", [])
        if affects and drug_code not in affects:
            continue

        relevant.append(s)

    return relevant


def get_context_multiplier(
    facility_id: str,
    facility_name: str,
    drug_code: str,
    drug_name: str,
    unit: str,
    baseline_rate: float,
    recent_14d: list[float],
    signals: list[dict[str, Any]],
) -> ContextResult:
    """Get LLM context multiplier with guardrails.

    Only calls LLM if there are relevant signals.
    """
    rel = relevant_signals(facility_id, drug_code, signals)

    if not rel:
        return ContextResult(
            multiplier=1.0, confidence=1.0, signal_ids=[],
            reasoning="No relevant signals", method="no_signal",
        )

    try:
        resp = httpx.post(
            f"{GENAI_URL}/llm/complete",
            json={
                "purpose": "forecast_context",
                "prompt_id": "forecast_ctx",
                "version": 1,
                "input": {
                    "facility_id": facility_id,
                    "facility_name": facility_name,
                    "drug_code": drug_code,
                    "drug_name": drug_name,
                    "unit": unit,
                    "baseline_rate": round(baseline_rate, 2),
                    "recent_series": recent_14d[-14:] if recent_14d else [],
                    "signals": [
                        {
                            "id": s["id"],
                            "type": s.get("type", "unknown"),
                            "params": s.get("params", {}),
                            "fired_at": s.get("fired_at", ""),
                        }
                        for s in rel
                    ],
                },
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("ok"):
            log.warning("genai_not_ok", error=data.get("error"))
            return _fallback_from_signals(rel)

        output = data.get("output", {})
        return apply_guardrails(output, rel)

    except Exception as e:
        log.warning("genai_call_failed", error=str(e))
        return _fallback_from_signals(rel)


def apply_guardrails(
    llm_output: dict[str, Any],
    available_signals: list[dict[str, Any]],
) -> ContextResult:
    """Clamp multiplier, validate signal citations."""
    raw_mult = llm_output.get("multiplier", 1.0)
    confidence = llm_output.get("confidence", 0.0)
    signal_ids = llm_output.get("signal_ids", [])
    reasoning = llm_output.get("reasoning", "")

    # Clamp
    multiplier = max(MULTIPLIER_MIN, min(MULTIPLIER_MAX, float(raw_mult)))

    # Validate signal IDs
    valid_ids = {s["id"] for s in available_signals}
    cited = [sid for sid in signal_ids if sid in valid_ids]

    # Guard: no valid citation or low confidence → 1.0
    if not cited or confidence < CONFIDENCE_THRESHOLD:
        return ContextResult(
            multiplier=1.0, confidence=confidence, signal_ids=[],
            reasoning=f"Guardrail: {'no valid signal cited' if not cited else 'low confidence'}",
            method="guardrail_fallback",
        )

    return ContextResult(
        multiplier=multiplier,
        confidence=confidence,
        signal_ids=cited,
        reasoning=reasoning,
        method="llm",
    )


def _fallback_from_signals(signals: list[dict[str, Any]]) -> ContextResult:
    """Deterministic fallback when LLM is unavailable: use signal params."""
    max_factor = 1.0
    ids = []
    for s in signals:
        factor = s.get("params", {}).get("demand_multiplier",
                 s.get("params", {}).get("factor", 1.0))
        if factor > max_factor:
            max_factor = factor
            ids = [s["id"]]

    multiplier = max(MULTIPLIER_MIN, min(MULTIPLIER_MAX, max_factor))
    return ContextResult(
        multiplier=multiplier,
        confidence=0.6,
        signal_ids=ids,
        reasoning="Deterministic fallback from signal params",
        method="guardrail_fallback",
    )
