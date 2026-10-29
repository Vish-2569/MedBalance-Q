"""Copilot tool definitions and executors.

Each tool maps to a real HTTP call against core-api, optimizer, or coldchain.
In fixture mode, returns canned data so tests run without live services.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Coroutine

import httpx

from medbal_common.logging import get_logger
from medbal_common.settings import settings

log = get_logger("genai.copilot_tools")


def _use_fixtures() -> bool:
    return os.environ.get("USE_FIXTURES", "").lower() in ("1", "true") or settings.USE_FIXTURES

CORE_API_URL = os.environ.get("CORE_API_URL", "http://core-api:8001")
OPTIMIZER_URL = os.environ.get("OPTIMIZER_URL", "http://optimizer:8005")
COLDCHAIN_URL = os.environ.get("COLDCHAIN_URL", "http://coldchain:8006")
TOOL_TIMEOUT = 10.0

# ── Tool JSON-schema definitions (passed to the LLM) ─────────────

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_district_overview",
        "description": (
            "Get a summary of all facilities, stock positions, total shortages "
            "and at-risk quantities across the district."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_stock_position",
        "description": (
            "Get the FEFO stock position for a specific facility and drug, "
            "including effective stock, at-risk, reserve, shortage, and lot details."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "facility": {
                    "type": "string",
                    "description": "Facility code, e.g. 'H1', 'W0'.",
                },
                "drug": {
                    "type": "string",
                    "description": "Drug code, e.g. 'INSUL', 'PARA500'.",
                },
            },
            "required": ["facility", "drug"],
        },
    },
    {
        "name": "explain_order",
        "description": (
            "Get full details and provenance of a transfer order including "
            "DTA number, source, destination, qty, usable, status, and audit trail."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order ID, e.g. 'ORD-001'.",
                },
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "why_not",
        "description": (
            "Explain why a facility did not receive a particular drug. "
            "Returns residual shortage and every candidate source lot "
            "with the feasibility rules that blocked it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "facility": {
                    "type": "string",
                    "description": "Destination facility code, e.g. 'H4'.",
                },
                "drug": {
                    "type": "string",
                    "description": "Drug code, e.g. 'INSUL'.",
                },
            },
            "required": ["facility", "drug"],
        },
    },
    {
        "name": "what_if",
        "description": (
            "Run a hypothetical scenario on the current plan. "
            "Applies overrides to a snapshot copy and re-runs the optimizer. "
            "Returns the diff: orders added/removed, KPI deltas. "
            "Available actions: add_vehicle, remove_vehicle, close_route, "
            "open_route, set_reserve_days, delay_days, repair_cold_storage, "
            "break_cold_storage, set_multiplier."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "overrides": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "description": (
                            "Override object with 'action' key and action-specific params. "
                            "E.g. {\"action\": \"repair_cold_storage\", \"facility\": \"H4\"}."
                        ),
                    },
                    "description": "List of override actions to apply.",
                },
            },
            "required": ["overrides"],
        },
    },
    {
        "name": "get_coldchain_status",
        "description": (
            "Get the current cold-chain monitoring status: device list with "
            "temperatures, battery levels, alert states, and breach history."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_audit_trail",
        "description": (
            "Get the audit trail for a specific transfer order, showing every "
            "state change with actor, action, timestamp, and hash."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order ID, e.g. 'ORD-001'.",
                },
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "compare_policies",
        "description": (
            "Compare min-reserve and target-days policies across all facilities "
            "and drugs. Shows which facilities have stricter or looser thresholds."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

# ── Fixture data for testing ──────────────────────────────────────

_FIXTURE_FACILITIES = [
    {"id": "W0", "name": "SIM-District Warehouse", "type": "warehouse", "cold_storage": True},
    {"id": "H1", "name": "SIM-City Hospital", "type": "hospital", "cold_storage": True},
    {"id": "H2", "name": "SIM-General Hospital", "type": "hospital", "cold_storage": True},
    {"id": "H3", "name": "SIM-Community Health Centre", "type": "hospital", "cold_storage": False},
    {"id": "H4", "name": "SIM-Primary Health Centre", "type": "hospital", "cold_storage": False},
]

_FIXTURE_POSITIONS = [
    {"facility_id": "W0", "drug_code": "PARA500", "effective_stock": 2000, "at_risk": 0, "reserve": 200, "shortage": 0, "consumption_rate": 0.0},
    {"facility_id": "W0", "drug_code": "INSUL", "effective_stock": 50, "at_risk": 0, "reserve": 5, "shortage": 0, "consumption_rate": 0.0},
    {"facility_id": "H1", "drug_code": "PARA500", "effective_stock": 100, "at_risk": 50, "reserve": 60, "shortage": 80, "consumption_rate": 8.0},
    {"facility_id": "H1", "drug_code": "INSUL", "effective_stock": 10, "at_risk": 5, "reserve": 6, "shortage": 8, "consumption_rate": 0.5},
    {"facility_id": "H2", "drug_code": "PARA500", "effective_stock": 50, "at_risk": 0, "reserve": 60, "shortage": 130, "consumption_rate": 6.0},
    {"facility_id": "H2", "drug_code": "INSUL", "effective_stock": 0, "at_risk": 0, "reserve": 0, "shortage": 15, "consumption_rate": 0.5},
    {"facility_id": "H3", "drug_code": "AMOX500", "effective_stock": 0, "at_risk": 0, "reserve": 0, "shortage": 120, "consumption_rate": 4.0},
    {"facility_id": "H3", "drug_code": "ORS", "effective_stock": 20, "at_risk": 10, "reserve": 50, "shortage": 100, "consumption_rate": 5.0},
    {"facility_id": "H4", "drug_code": "PARA500", "effective_stock": 80, "at_risk": 0, "reserve": 30, "shortage": 40, "consumption_rate": 4.0},
]

_FIXTURE_ORDERS: dict[str, dict[str, Any]] = {
    "ORD-001": {
        "id": "ORD-001", "dta_number": "DTA/BLR-U/2026/000001",
        "plan_id": "plan-demo-001", "src_facility_id": "W0", "dst_facility_id": "H2",
        "drug_code": "PARA500", "drug_name": "Paracetamol 500mg",
        "batch_no": "B-PA-2026-001", "qty": 180, "usable": 180, "score": 0.92,
        "status": "proposed", "temperature_req": "ambient",
    },
    "ORD-005": {
        "id": "ORD-005", "dta_number": "DTA/BLR-U/2026/000005",
        "plan_id": "plan-demo-001", "src_facility_id": "W0", "dst_facility_id": "H2",
        "drug_code": "INSUL", "drug_name": "Insulin Human 40IU/ml",
        "batch_no": "B-IN-2026-001", "qty": 28, "usable": 28, "score": 0.88,
        "status": "proposed", "temperature_req": "cold_chain",
    },
}

_FIXTURE_WHYNOT = {
    ("H4", "INSUL"): {
        "facility_id": "H4", "drug_code": "INSUL",
        "residual_shortage": 0, "supplied": 0,
        "candidates": [
            {
                "src_facility_id": "W0", "batch_no": "B-IN-2026-001",
                "qty": 50, "usable": 0, "feasible": False,
                "failed_rules": ["F3: H4 (SIM-Primary Health Centre) has no cold storage"],
                "net_score": 0.0,
            }
        ],
    },
    ("H3", "INSUL"): {
        "facility_id": "H3", "drug_code": "INSUL",
        "residual_shortage": 0, "supplied": 0,
        "candidates": [
            {
                "src_facility_id": "W0", "batch_no": "B-IN-2026-001",
                "qty": 50, "usable": 0, "feasible": False,
                "failed_rules": ["F3: H3 (SIM-Community Health Centre) has no cold storage"],
                "net_score": 0.0,
            }
        ],
    },
}

_FIXTURE_WHATIF = {
    "repair_cold_storage": {
        "baseline": {"shortage_reduction": 0.72, "expiry_avoided": 215, "cost_inr": 1250.0, "trips": 6},
        "scenario": {"shortage_reduction": 0.85, "expiry_avoided": 243, "cost_inr": 1420.0, "trips": 7},
        "diff": {
            "shortage_reduction_delta": 0.13,
            "expiry_avoided_delta": 28,
            "cost_delta": 170.0,
            "trips_delta": 1,
            "orders_added": [
                {"dst_facility_id": "H4", "drug_code": "INSUL", "qty": 28, "usable": 28},
            ],
            "orders_removed": [],
        },
    },
}

_FIXTURE_COLDCHAIN = [
    {"device_id": "sensor-01", "vehicle_id": "V1", "temperature_c": 4.2, "battery_pct": 87, "state": "ok", "alert": False},
    {"device_id": "sensor-02", "vehicle_id": "V1", "temperature_c": 5.1, "battery_pct": 92, "state": "ok", "alert": False},
]

_FIXTURE_AUDIT: dict[str, list[dict[str, Any]]] = {
    "ORD-001": [
        {"seq": 2, "actor": "optimizer", "action": "propose", "entity": "order",
         "entity_id": "ORD-001", "payload": {"drug_code": "PARA500", "qty": 180, "src": "W0", "dst": "H2"},
         "created_at": "2026-11-01T10:30:01+05:30"},
    ],
    "ORD-005": [
        {"seq": 6, "actor": "optimizer", "action": "propose", "entity": "order",
         "entity_id": "ORD-005", "payload": {"drug_code": "INSUL", "qty": 28, "src": "W0", "dst": "H2"},
         "created_at": "2026-11-01T10:30:05+05:30"},
    ],
}

_FIXTURE_POLICIES = [
    {"facility_id": "H1", "drug_code": "PARA500", "min_reserve_days": 7, "target_days": 30},
    {"facility_id": "H1", "drug_code": "INSUL", "min_reserve_days": 14, "target_days": 30},
    {"facility_id": "H2", "drug_code": "PARA500", "min_reserve_days": 7, "target_days": 30},
    {"facility_id": "H2", "drug_code": "INSUL", "min_reserve_days": 14, "target_days": 30},
    {"facility_id": "H3", "drug_code": "AMOX500", "min_reserve_days": 7, "target_days": 30},
    {"facility_id": "H3", "drug_code": "ORS", "min_reserve_days": 7, "target_days": 30},
    {"facility_id": "H4", "drug_code": "PARA500", "min_reserve_days": 7, "target_days": 30},
]


# ── HTTP helpers ──────────────────────────────────────────────────

async def _get(url: str, params: dict[str, str] | None = None) -> dict[str, Any] | list | None:
    try:
        async with httpx.AsyncClient(timeout=TOOL_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}", "url": url}
    except Exception as exc:
        log.warning("tool_http_error", url=url, error=str(exc))
        return {"error": f"Service unavailable: {exc}", "url": url}


async def _post(url: str, json_body: dict[str, Any]) -> dict[str, Any] | list | None:
    try:
        async with httpx.AsyncClient(timeout=TOOL_TIMEOUT) as client:
            resp = await client.post(url, json=json_body)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"HTTP {resp.status_code}", "url": url}
    except Exception as exc:
        log.warning("tool_http_error", url=url, error=str(exc))
        return {"error": f"Service unavailable: {exc}", "url": url}


# ── Tool executors ────────────────────────────────────────────────

async def _exec_get_district_overview(_args: dict[str, Any]) -> dict[str, Any]:
    if _use_fixtures():
        positions = _FIXTURE_POSITIONS
        facilities = _FIXTURE_FACILITIES
    else:
        facilities = await _get(f"{CORE_API_URL}/facilities") or []
        positions = await _get(f"{CORE_API_URL}/positions") or []

    if isinstance(facilities, dict) and "error" in facilities:
        return facilities
    if isinstance(positions, dict) and "error" in positions:
        return positions

    total_shortage = sum(p.get("shortage", 0) for p in positions)
    total_at_risk = sum(p.get("at_risk", 0) for p in positions)
    drugs = sorted({p.get("drug_code", "") for p in positions})

    return {
        "facilities": [
            {"id": f["id"], "name": f["name"], "type": f.get("type", ""), "cold_storage": f.get("cold_storage")}
            for f in facilities
        ],
        "drug_codes": drugs,
        "total_positions": len(positions),
        "total_shortage": total_shortage,
        "total_at_risk": total_at_risk,
    }


async def _exec_get_stock_position(args: dict[str, Any]) -> dict[str, Any]:
    facility = args.get("facility", "")
    drug = args.get("drug", "")

    if _use_fixtures():
        matches = [
            p for p in _FIXTURE_POSITIONS
            if p["facility_id"] == facility and p["drug_code"] == drug
        ]
        return matches[0] if matches else {"error": f"No position for {facility}/{drug}"}

    result = await _get(f"{CORE_API_URL}/positions", {"facility": facility, "drug": drug})
    if isinstance(result, list):
        return result[0] if result else {"error": f"No position for {facility}/{drug}"}
    return result or {"error": "No data"}


async def _exec_explain_order(args: dict[str, Any]) -> dict[str, Any]:
    order_id = args.get("order_id", "")

    if _use_fixtures():
        order = _FIXTURE_ORDERS.get(order_id)
        if not order:
            return {"error": f"Order {order_id} not found"}
        provenance = _FIXTURE_AUDIT.get(order_id, [])
        return {"order": order, "audit": provenance}

    order = await _get(f"{CORE_API_URL}/orders/{order_id}")
    provenance = await _get(f"{CORE_API_URL}/provenance/{order_id}")
    if isinstance(order, dict) and "error" in order:
        return order
    return {"order": order, "audit": provenance}


async def _exec_why_not(args: dict[str, Any]) -> dict[str, Any]:
    facility = args.get("facility", "")
    drug = args.get("drug", "")

    if _use_fixtures():
        result = _FIXTURE_WHYNOT.get((facility, drug))
        return result or {"facility_id": facility, "drug_code": drug, "residual_shortage": 0, "candidates": []}

    result = await _get(f"{OPTIMIZER_URL}/whynot", {"facility": facility, "drug": drug})
    return result or {"error": "No data"}


async def _exec_what_if(args: dict[str, Any]) -> dict[str, Any]:
    overrides = args.get("overrides", [])

    if _use_fixtures():
        for ov in overrides:
            action = ov.get("action", "")
            if action in _FIXTURE_WHATIF:
                return _FIXTURE_WHATIF[action]
        return {"diff": {"orders_added": [], "orders_removed": [], "shortage_reduction_delta": 0}}

    result = await _post(f"{OPTIMIZER_URL}/whatif", {"overrides": overrides})
    return result or {"error": "No data"}


async def _exec_get_coldchain_status(_args: dict[str, Any]) -> dict[str, Any]:
    if _use_fixtures():
        return {"devices": _FIXTURE_COLDCHAIN}

    result = await _get(f"{COLDCHAIN_URL}/status")
    if isinstance(result, list):
        return {"devices": result}
    return result or {"devices": []}


async def _exec_get_audit_trail(args: dict[str, Any]) -> dict[str, Any]:
    order_id = args.get("order_id", "")

    if _use_fixtures():
        entries = _FIXTURE_AUDIT.get(order_id, [])
        return {"order_id": order_id, "entries": entries}

    result = await _get(f"{CORE_API_URL}/audit", {"entity": "transfer_order", "id": order_id})
    if isinstance(result, list):
        return {"order_id": order_id, "entries": result}
    return result or {"order_id": order_id, "entries": []}


async def _exec_compare_policies(_args: dict[str, Any]) -> dict[str, Any]:
    if _use_fixtures():
        return {"policies": _FIXTURE_POLICIES}

    snapshot = await _get(f"{CORE_API_URL}/snapshot")
    if not isinstance(snapshot, dict):
        return {"error": "Could not fetch snapshot"}
    if "error" in snapshot:
        return snapshot

    policies_raw = snapshot.get("policies", [])
    policies = [
        {
            "facility_id": p.get("facility_id"),
            "drug_code": p.get("drug_code"),
            "min_reserve_days": p.get("min_reserve_days"),
            "target_days": p.get("target_days"),
        }
        for p in policies_raw
    ]
    return {"policies": policies}


# ── Registry ──────────────────────────────────────────────────────

TOOL_MAP: dict[str, Callable[..., Coroutine[Any, Any, dict[str, Any]]]] = {
    "get_district_overview": _exec_get_district_overview,
    "get_stock_position": _exec_get_stock_position,
    "explain_order": _exec_explain_order,
    "why_not": _exec_why_not,
    "what_if": _exec_what_if,
    "get_coldchain_status": _exec_get_coldchain_status,
    "get_audit_trail": _exec_get_audit_trail,
    "compare_policies": _exec_compare_policies,
}


async def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a copilot tool by name. Returns result dict; never raises."""
    executor = TOOL_MAP.get(name)
    if not executor:
        return {"error": f"Unknown tool: {name}"}
    try:
        result = await executor(args)
        return result if isinstance(result, dict) else {"data": result}
    except Exception as exc:
        log.warning("tool_execution_error", tool=name, error=str(exc))
        return {"error": f"Tool {name} failed: {exc}"}
