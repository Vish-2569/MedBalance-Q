from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..clock_state import clock

router = APIRouter()


class SpeedRequest(BaseModel):
    speed: float


@router.get("/clock")
async def get_clock():
    return clock.to_dict()


@router.post("/clock/start")
async def start_clock():
    clock.start()
    return clock.to_dict()


@router.post("/clock/pause")
async def pause_clock():
    clock.pause()
    return clock.to_dict()


@router.post("/clock/speed")
async def set_speed(body: SpeedRequest):
    clock.set_speed(body.speed)
    return clock.to_dict()
