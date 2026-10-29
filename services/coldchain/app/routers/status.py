"""GET /status and GET /devices/{id}/telemetry endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..mqtt_consumer import get_machines, get_store

router = APIRouter()


@router.get("/status")
async def device_status():
    machines = get_machines()
    return [m.to_status() for m in machines.values()]


@router.get("/devices/{device_id}/telemetry")
async def device_telemetry(
    device_id: str,
    since: str | None = Query(None),
):
    store = get_store()
    machines = get_machines()
    if device_id not in machines:
        raise HTTPException(404, f"Unknown device {device_id}")
    return store.get(device_id, since=since)
