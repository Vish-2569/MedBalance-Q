"""GET /snapshot — full state for the optimizer."""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from medbal_common.db import session_scope
from medbal_common.clock import today

from ..queries import (
    list_facilities,
    list_drugs,
    list_routes,
    list_vehicles,
    list_lots,
    list_policies,
    list_forecasts,
)
from .positions import _compute_all_positions

router = APIRouter()


@router.get("/snapshot")
async def get_snapshot():
    t = today()
    with session_scope() as s:
        snap = {
            "today": t.isoformat(),
            "facilities": list_facilities(s),
            "drugs": list_drugs(s),
            "routes": list_routes(s),
            "vehicles": list_vehicles(s),
            "lots": list_lots(s),
            "positions": _compute_all_positions(s, t),
            "forecasts": list_forecasts(s),
            "policies": list_policies(s),
        }
    canonical = json.dumps(snap, sort_keys=True, separators=(",", ":"))
    snap["snapshot_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
    return JSONResponse(snap)
