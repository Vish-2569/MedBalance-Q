from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from medbal_common.auth import CurrentUser, require_role

from ..clock_state import clock

router = APIRouter()


class SpeedRequest(BaseModel):
    speed: float


@router.get("/clock")
async def get_clock():
    return clock.to_dict()


@router.post("/clock/start")
async def start_clock(
    user: CurrentUser = Depends(require_role("operator", "admin")),
):
    clock.start()
    return clock.to_dict()


@router.post("/clock/pause")
async def pause_clock(
    user: CurrentUser = Depends(require_role("operator", "admin")),
):
    clock.pause()
    return clock.to_dict()


@router.post("/clock/speed")
async def set_speed(
    body: SpeedRequest,
    user: CurrentUser = Depends(require_role("operator", "admin")),
):
    clock.set_speed(body.speed)
    return clock.to_dict()
