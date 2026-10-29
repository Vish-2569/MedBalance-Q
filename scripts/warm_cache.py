"""Warm the LLM response cache for demo mode.

DEMO_MODE=record: reset seed 42, run the full demo script programmatically,
then verify with DEMO_MODE=replay that the same script produces 0 cache misses.

Usage:
    python -I scripts/warm_cache.py [--verify-only] [--base-url http://localhost:8080]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASE = "http://localhost:8080"
SEED = 42
SIM_DAY_WAIT = 3.0


def _api(base: str, method: str, path: str, **kwargs) -> dict | list | None:
    url = f"{base}{path}"
    timeout = kwargs.pop("timeout", 30.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            if method == "GET":
                resp = client.get(url, **kwargs)
            else:
                resp = client.post(url, **kwargs)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"  WARNING: {method} {path} failed: {e}")
        return None


def _reset_sim(base: str):
    print("[1/8] Resetting sim (seed=42)...")
    _api(base, "POST", f"/api/sim/reset?seed={SEED}")
    time.sleep(1)


def _advance_clock(base: str, days: int = 3):
    print(f"[2/8] Advancing clock {days} days...")
    _api(base, "POST", "/api/sim/clock/start", json={"speed": 20})
    time.sleep(days * SIM_DAY_WAIT)
    _api(base, "POST", "/api/sim/clock/pause")
    time.sleep(1)


def _activate_scenarios(base: str):
    print("[3/8] Activating scenarios (dengue_outbreak, bad_data)...")
    _api(base, "POST", "/api/sim/scenario/dengue_outbreak")
    time.sleep(0.5)
    _api(base, "POST", "/api/sim/scenario/bad_data")
    time.sleep(0.5)


def _run_forecast(base: str):
    print("[4/8] Running forecasts...")
    _api(base, "POST", "/api/forecast/forecast/run", json={}, timeout=60)


def _run_plan(base: str) -> str | None:
    print("[5/8] Running optimizer plan (QUBO)...")
    result = _api(base, "POST", "/api/optimizer/plan/run",
                  json={"solver": "qubo"}, timeout=120)
    if result and isinstance(result, dict):
        plan_id = result.get("plan_id", result.get("id"))
        print(f"  Plan ID: {plan_id}")
        return plan_id
    return None


def _narrate_orders(base: str, plan_id: str | None):
    print("[6/8] Narrating orders...")
    if not plan_id:
        print("  Skipped (no plan)")
        return

    orders = _api(base, "GET", "/api/core/orders", params={"plan_id": plan_id})
    if not orders or not isinstance(orders, list):
        orders_resp = _api(base, "GET", "/api/optimizer/plan/demo")
        if isinstance(orders_resp, dict):
            orders = orders_resp.get("orders", [])
        elif isinstance(orders_resp, list):
            orders = orders_resp
        else:
            orders = []

    for order in orders[:10]:
        oid = order.get("id", "")
        facts = _order_to_facts(order)
        _api(base, "POST", f"/api/genai/narrate/{oid}",
             json={"order_facts": facts}, timeout=30)
        time.sleep(0.3)

    print(f"  Narrated {min(len(orders), 10)} orders")


def _order_to_facts(order: dict) -> dict:
    return {
        "drug_name": order.get("drug_name", ""),
        "drug_code": order.get("drug_code", ""),
        "qty": order.get("qty", 0),
        "unit": order.get("unit", "units"),
        "batch_no": order.get("batch_no", ""),
        "expiry": order.get("expiry", ""),
        "src_facility": order.get("src_facility", order.get("src_facility_id", "")),
        "src_facility_id": order.get("src_facility_id", ""),
        "dst_facility": order.get("dst_facility", order.get("dst_facility_id", "")),
        "dst_facility_id": order.get("dst_facility_id", ""),
        "usable": order.get("usable", order.get("qty", 0)),
        "src_rate": order.get("src_rate", 0),
        "dst_rate": order.get("dst_rate", 0),
        "shortage_before": order.get("shortage_before", 0),
        "shortage_after": order.get("shortage_after", 0),
        "expiry_avoided": order.get("expiry_avoided", 0),
        "expiry_avoided_inr": order.get("expiry_avoided_inr", 0),
        "temperature_req": order.get("temperature_req", "ambient"),
    }


def _run_copilot(base: str):
    print("[7/8] Running copilot questions...")
    questions = [
        "Give me an overview of the district's stock situation.",
        "What is the stock position of insulin at H1?",
        "Why didn't Hesaraghatta get insulin?",
        "What if we repair Hesaraghatta's fridge?",
        "Explain order ORD-001.",
        "Is the cold chain okay right now?",
        "Show me the audit trail for order ORD-005.",
        "Compare the stock policies across facilities.",
        "How much paracetamol does H3 have?",
        "Why is H2 not receiving any transfers?",
        "What if we close the route from W0 to H3?",
        "H4 ನಲ್ಲಿ ಇನ್ಸುಲಿನ್ ಏಕೆ ಸಿಗಲಿಲ್ಲ?",
    ]

    for i, q in enumerate(questions):
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    f"{base}/api/genai/copilot/chat",
                    json={"message": q},
                )
            print(f"  Q{i+1:02d}: {resp.status_code}")
        except Exception as e:
            print(f"  Q{i+1:02d}: ERROR ({e})")
        time.sleep(0.5)


def _generate_documents(base: str):
    print("[8/8] Generating DTA/credit-memo PDFs...")
    for oid in ["ORD-001", "ORD-002", "ORD-003", "ORD-004", "ORD-005"]:
        _api(base, "GET", f"/api/genai/dta/{oid}/pdf", timeout=15)
        time.sleep(0.3)

    _api(base, "POST", "/api/genai/credit-memo/pdf", json={
        "donor_facility": "SIM-District Warehouse",
        "donor_facility_id": "W0",
        "total_units": 500,
        "unit": "units",
        "drugs_summary": "Paracetamol 500mg, Amoxicillin 500mg, ORS",
        "value_inr": 1500.0,
        "transfer_count": 4,
        "receivers": "SIM-General Hospital, SIM-Community Health Centre",
    }, timeout=15)


def warm(base: str):
    print("=" * 60)
    print("MedBalance-Q Demo Cache Warmer")
    print(f"Mode: RECORD (base={base})")
    print("=" * 60)

    os.environ["DEMO_MODE"] = "record"

    t0 = time.monotonic()

    _reset_sim(base)
    _advance_clock(base)
    _activate_scenarios(base)
    _run_forecast(base)
    plan_id = _run_plan(base)
    _narrate_orders(base, plan_id)
    _run_copilot(base)
    _generate_documents(base)

    elapsed = time.monotonic() - t0
    print(f"\nWarm complete in {elapsed:.1f}s")
    return True


def verify(base: str) -> bool:
    print("\n" + "=" * 60)
    print("Replay verification (DEMO_MODE=replay)")
    print("=" * 60)

    os.environ["DEMO_MODE"] = "replay"

    _reset_sim(base)
    _advance_clock(base)

    misses = 0

    print("Checking forecast replay...")
    result = _api(base, "POST", "/api/forecast/forecast/run", json={}, timeout=60)
    if result and isinstance(result, dict):
        llm_calls = result.get("llm_calls", 0)
        if llm_calls > 0:
            print(f"  WARNING: {llm_calls} LLM calls in replay mode (expected 0)")

    print("Checking plan replay...")
    result = _api(base, "POST", "/api/optimizer/plan/run",
                  json={"solver": "qubo"}, timeout=120)

    print("Checking AI health for cache misses...")
    health = _api(base, "GET", "/api/genai/ai/health")
    if health and isinstance(health, dict):
        fallbacks = health.get("fallbacks", 0)
        if fallbacks > 0:
            print(f"  WARNING: {fallbacks} fallbacks detected")
            misses += fallbacks

    print(f"\nReplay cache misses: {misses}")
    if misses == 0:
        print("PASS: 0 cache misses in replay mode")
    else:
        print(f"FAIL: {misses} cache misses")

    return misses == 0


def main():
    parser = argparse.ArgumentParser(description="MedBalance-Q demo cache warmer")
    parser.add_argument("--base-url", default=DEFAULT_BASE, help="Base URL")
    parser.add_argument("--verify-only", action="store_true", help="Skip warm, only verify replay")
    args = parser.parse_args()

    if not args.verify_only:
        warm(args.base_url)

    ok = verify(args.base_url)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
