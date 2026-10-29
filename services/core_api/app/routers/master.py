"""Master data endpoints: facilities, drugs, routes, vehicles."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from medbal_common.db import session_scope

from ..queries import list_facilities, list_drugs, list_routes, list_vehicles

router = APIRouter()


@router.get("/facilities")
async def get_facilities():
    with session_scope() as s:
        return JSONResponse(list_facilities(s))


@router.get("/drugs")
async def get_drugs():
    with session_scope() as s:
        return JSONResponse(list_drugs(s))


@router.get("/routes")
async def get_routes():
    with session_scope() as s:
        return JSONResponse(list_routes(s))


@router.get("/vehicles")
async def get_vehicles():
    with session_scope() as s:
        return JSONResponse(list_vehicles(s))
