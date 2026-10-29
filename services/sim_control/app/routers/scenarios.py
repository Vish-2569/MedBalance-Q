from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter, HTTPException, Query

from .. import scenario_defs
from ..clock_state import clock

router = APIRouter()


@router.get("/scenarios")
async def list_scenarios():
    return scenario_defs.list_scenarios()


@router.post("/scenario/{name}")
async def activate_scenario(name: str):
    try:
        scenario_defs.activate(name)
    except ValueError:
        raise HTTPException(404, f"Unknown scenario: {name}")
    return {"activated": name}


@router.get("/signals")
async def get_signals():
    return scenario_defs.get_signals(clock.day_index)


@router.post("/reset")
async def reset_sim(seed: int = Query(default=42)):
    clock.reset(seed)
    scenario_defs.reset_scenarios()
    async with httpx.AsyncClient(timeout=5.0) as client:
        tasks = []
        for i in range(1, 5):
            url = f"http://sim-hospital-h{i}:8101/reset"
            tasks.append(client.post(url))
        await asyncio.gather(*tasks, return_exceptions=True)
    return {"seed": seed, "sim_date": clock.sim_date.isoformat()}
