"""Auto re-plan: consume coldchain.alert, find affected orders, re-plan.

When a cold chain alert fires, find live not-yet-dispatched orders on the
affected vehicle/route, run what-if with those routes unsafe, and if valid,
persist as a revised plan.
"""
from __future__ import annotations

import uuid
from typing import Any

from medbal_common.logging import get_logger
from medbal_common import bus

from .baselines import TransferOrder
from .metrics import compute_metrics
from .snapshot import Snapshot
from .whatif import run_whatif

log = get_logger("optimizer.replan")


_live_plan: dict[str, Any] | None = None
_live_orders: list[TransferOrder] | None = None
_live_snap: Snapshot | None = None


def set_live_plan(
    plan: dict[str, Any],
    orders: list[TransferOrder],
    snap: Snapshot,
) -> None:
    global _live_plan, _live_orders, _live_snap
    _live_plan = plan
    _live_orders = orders
    _live_snap = snap


def get_live_plan() -> tuple[dict[str, Any] | None, list[TransferOrder] | None, Snapshot | None]:
    return _live_plan, _live_orders, _live_snap


def _find_affected_orders(
    orders: list[TransferOrder],
    snap: Snapshot,
    alert: dict[str, Any],
) -> list[TransferOrder]:
    """Find undispatched orders on the affected vehicle/routes."""
    device_id = alert.get("device_id", "")
    vehicle_id = alert.get("vehicle_id", "")

    affected_routes: set[tuple[str, str]] = set()

    for v in snap.vehicles:
        if v.id == vehicle_id or device_id.startswith(f"sensor-{v.id.lower()}"):
            if v.cold_chain:
                for (src, dst), route in snap.routes.items():
                    if route.cold_chain:
                        affected_routes.add((src, dst))

    affected: list[TransferOrder] = []
    for o in orders:
        if o.status != "proposed":
            continue
        if o.temperature_req == "cold_chain":
            route_key = (o.src_facility_id, o.dst_facility_id)
            if route_key in affected_routes or not affected_routes:
                affected.append(o)

    return affected


def _build_overrides_from_alert(
    alert: dict[str, Any],
    affected_orders: list[TransferOrder],
    snap: Snapshot,
) -> list[dict[str, Any]]:
    """Build what-if overrides that make affected routes unsafe."""
    overrides: list[dict[str, Any]] = []

    vehicle_id = alert.get("vehicle_id", "")
    if vehicle_id:
        overrides.append({"action": "remove_vehicle", "id": vehicle_id})

    seen_routes: set[tuple[str, str]] = set()
    for o in affected_orders:
        key = (o.src_facility_id, o.dst_facility_id)
        if key not in seen_routes:
            seen_routes.add(key)

    return overrides


def handle_coldchain_alert(alert: dict[str, Any]) -> dict[str, Any] | None:
    """Handle a coldchain.alert event. Returns revised plan diff or None."""
    plan, orders, snap = get_live_plan()
    if plan is None or orders is None or snap is None:
        log.info("replan_skip_no_live_plan")
        return None

    affected = _find_affected_orders(orders, snap, alert)
    if not affected:
        log.info("replan_skip_no_affected_orders", device=alert.get("device_id"))
        return None

    log.info(
        "replan_triggered",
        device=alert.get("device_id"),
        vehicle=alert.get("vehicle_id"),
        affected_orders=len(affected),
    )

    overrides = _build_overrides_from_alert(alert, affected, snap)
    if not overrides:
        log.info("replan_skip_no_overrides")
        return None

    try:
        diff = run_whatif(overrides, snap, orders, solver="qubo", timeout=30.0)
    except Exception as exc:
        log.error("replan_whatif_failed", error=str(exc))
        return None

    wi_orders_data = diff.get("whatif_orders", [])
    if not wi_orders_data:
        log.info("replan_whatif_empty")
        return None

    revised_plan_id = f"plan-rev-{uuid.uuid4().hex[:8]}"
    old_plan_id = plan.get("id", "unknown")

    changes: list[dict[str, Any]] = []
    for c in diff.get("changes", []):
        changes.append({
            "order_id": c.get("order_id", ""),
            "field": c.get("type", ""),
            "old_value": c.get("qty_old") or c.get("qty"),
            "new_value": c.get("qty_new") or c.get("qty"),
        })

    for o in affected:
        o.status = "superseded"

    revised_event = {
        "plan_id": revised_plan_id,
        "original_plan_id": old_plan_id,
        "reason": f"coldchain alert: {alert.get('device_id', 'unknown')} {alert.get('severity', '')}",
        "changes": changes,
        "kpi_delta": diff.get("kpi_delta", {}),
        "affected_orders": [o.id for o in affected],
    }

    _persist_revised(revised_plan_id, diff, revised_event)

    try:
        bus.publish("plan.revised", revised_event)
        log.info("replan_published", plan_id=revised_plan_id)
    except Exception as exc:
        log.warning("replan_publish_failed", error=str(exc))

    return revised_event


def _persist_revised(
    plan_id: str,
    diff: dict[str, Any],
    event: dict[str, Any],
) -> None:
    """Persist revised plan to core-api (best-effort)."""
    import httpx

    CORE_API_URL = "http://core-api:8001"

    revised_plan = {
        "plan": {
            "id": plan_id,
            "mode": "revised",
            "solver_tier": diff.get("solver_meta", {}).get("solver_tier", ""),
            "transfers": len(diff.get("whatif_orders", [])),
        },
        "orders": diff.get("whatif_orders", []),
        "revision": event,
    }

    try:
        httpx.post(
            f"{CORE_API_URL}/plans",
            json=revised_plan,
            timeout=10.0,
        )
    except Exception as exc:
        log.warning("persist_revised_failed", error=str(exc))
