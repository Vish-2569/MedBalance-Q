from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"
_DOCKER_DIR = Path("/app/contracts/fixtures")
CONTRACTS_DIR = _DOCKER_DIR if _DOCKER_DIR.exists() else _DEFAULT_DIR


def _load(filename: str) -> Any:
    path = CONTRACTS_DIR / filename
    if not path.exists():
        return {"error": f"fixture {filename} not found"}
    return json.loads(path.read_text(encoding="utf-8"))


def _find_by_id(data: Any, key: str, value: str) -> Any:
    if isinstance(data, list):
        for item in data:
            if item.get(key) == value:
                return item
        return data[0] if data else {"error": "not found"}
    return data


def serve(app: FastAPI, service_name: str) -> None:
    """Register fixture routes for a service when USE_FIXTURES=1."""
    _REGISTRARS.get(service_name, _noop)(app)


def _noop(app: FastAPI) -> None:
    pass


def _core_api(app: FastAPI) -> None:
    @app.get("/facilities")
    async def f1():
        return JSONResponse(_load("facilities.json"))

    @app.get("/drugs")
    async def f2():
        return JSONResponse(_load("drugs.json"))

    @app.get("/routes")
    async def f3():
        return JSONResponse(_load("routes.json"))

    @app.get("/vehicles")
    async def f4():
        return JSONResponse(_load("vehicles.json"))

    @app.get("/lots")
    async def f5(facility: str | None = None, drug: str | None = None):
        data = _load("lots.json")
        if isinstance(data, list):
            if facility:
                data = [l for l in data if l.get("facility_id") == facility]
            if drug:
                data = [l for l in data if l.get("drug_code") == drug]
        return JSONResponse(data)

    @app.get("/positions")
    async def f6(facility: str | None = None, drug: str | None = None):
        data = _load("positions.json")
        if isinstance(data, list):
            if facility:
                data = [p for p in data if p.get("facility_id") == facility]
            if drug:
                data = [p for p in data if p.get("drug_code") == drug]
        return JSONResponse(data)

    @app.get("/snapshot")
    async def f7():
        return JSONResponse(_load("snapshot.json"))

    @app.get("/orders")
    async def f8(plan_id: str | None = None, status: str | None = None):
        data = _load("orders.json")
        if isinstance(data, list):
            if plan_id:
                data = [o for o in data if o.get("plan_id") == plan_id]
            if status:
                data = [o for o in data if o.get("status") == status]
        return JSONResponse(data)

    @app.get("/orders/{id}")
    async def f9(id: str):
        return JSONResponse(_find_by_id(_load("orders.json"), "id", id))

    @app.get("/custody/{order_id}")
    async def f10(order_id: str):
        return JSONResponse(_load("custody.json"))

    @app.get("/audit/verify")
    async def f11():
        return JSONResponse(_load("audit-verify.json"))

    @app.get("/audit")
    async def f12(entity: str | None = None, id: str | None = None):
        return JSONResponse(_load("audit.json"))

    @app.get("/provenance/{order_id}")
    async def f13(order_id: str):
        order = _find_by_id(_load("orders.json"), "id", order_id)
        return JSONResponse({
            "order": order,
            "custody": _load("custody.json"),
            "audit": _load("audit.json"),
        })


def _ingest_ai(app: FastAPI) -> None:
    @app.get("/reports")
    async def f1(facility: str | None = None, since: str | None = None):
        return JSONResponse(_load("reports.json"))

    @app.get("/reviews")
    async def f2():
        return JSONResponse(_load("reviews.json"))


def _genai(app: FastAPI) -> None:
    @app.post("/llm/complete")
    async def f1():
        return JSONResponse(_load("llm-complete.json"))

    @app.post("/narrate/{order_id}")
    async def f2(order_id: str):
        return JSONResponse(_load("narration.json"))


def _forecast(app: FastAPI) -> None:
    @app.get("/forecast")
    async def f1(facility: str | None = None, drug: str | None = None):
        data = _load("forecasts.json")
        if isinstance(data, list):
            if facility:
                data = [f for f in data if f.get("facility_id") == facility]
            if drug:
                data = [f for f in data if f.get("drug_code") == drug]
        return JSONResponse(data)

    @app.get("/forecast/backtest")
    async def f2():
        return JSONResponse(_load("backtest.json"))


def _optimizer(app: FastAPI) -> None:
    @app.get("/plan/{id}")
    async def f1(id: str):
        return JSONResponse(_load("plan-demo.json"))

    @app.get("/plan/{id}/benchmark")
    async def f2(id: str):
        return JSONResponse(_load("benchmark.json"))

    @app.get("/plan/{id}/regret")
    async def f3(id: str, order_id: str | None = None):
        data = _load("plan-demo.json")
        regret = data.get("regret", []) if isinstance(data, dict) else []
        if order_id:
            regret = [r for r in regret if r.get("order_id") == order_id]
        return JSONResponse(regret)

    @app.get("/whynot")
    async def f4(facility: str | None = None, drug: str | None = None):
        return JSONResponse(_load("whynot.json"))

    @app.get("/eval/{id}")
    async def f5(id: str):
        return JSONResponse(_load("eval.json"))


def _coldchain(app: FastAPI) -> None:
    @app.get("/status")
    async def f1():
        return JSONResponse(_load("coldchain-status.json"))

    @app.get("/devices/{id}/telemetry")
    async def f2(id: str, since: str | None = None):
        return JSONResponse(_load("telemetry.json"))


def _sim_control(app: FastAPI) -> None:
    @app.get("/clock")
    async def f1():
        return JSONResponse(_load("clock.json"))

    @app.get("/scenarios")
    async def f2():
        return JSONResponse(_load("scenarios.json"))

    @app.get("/signals")
    async def f3():
        return JSONResponse(_load("signals.json"))


def _sim_hospital(app: FastAPI) -> None:
    @app.get("/state")
    async def f1():
        return JSONResponse(_load("sim-hospital-state.json"))


_REGISTRARS: dict[str, Any] = {
    "core-api": _core_api,
    "ingest-ai": _ingest_ai,
    "genai": _genai,
    "forecast": _forecast,
    "optimizer": _optimizer,
    "coldchain": _coldchain,
    "sim-control": _sim_control,
    "sim-hospital": _sim_hospital,
}
