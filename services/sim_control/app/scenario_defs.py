from __future__ import annotations

import json

from pydantic import BaseModel

from medbal_common import bus


class DemandMult(BaseModel):
    facility: str
    drug_code: str
    multiplier: float
    start_day: int
    end_day: int


class SignalDef(BaseModel):
    id: str
    type: str
    facility: str | None = None
    drugs_affected: list[str] = []
    text: str
    start_day: int


class ScenarioDef(BaseModel):
    name: str
    description: str
    demand_multipliers: list[DemandMult] = []
    device_faults: list[dict] = []
    route_closures: list[str] = []
    signals: list[SignalDef] = []


SCENARIOS: dict[str, ScenarioDef] = {
    "baseline": ScenarioDef(
        name="baseline",
        description="Normal operations, no interventions",
    ),
    "dengue_outbreak": ScenarioDef(
        name="dengue_outbreak",
        description="Dengue outbreak at SIM-CHC Yelahanka (H3)",
        demand_multipliers=[
            DemandMult(facility="H3", drug_code="ORS", multiplier=3.0, start_day=5, end_day=15),
            DemandMult(facility="H3", drug_code="PCM", multiplier=3.0, start_day=5, end_day=15),
        ],
        signals=[SignalDef(
            id="sig-dengue", type="outbreak", facility="H3",
            drugs_affected=["ORS", "PCM"],
            text="IDSP alert: dengue cluster in Yelahanka zone, 23 confirmed cases",
            start_day=5,
        )],
    ),
    "fridge_failure": ScenarioDef(
        name="fridge_failure",
        description="Cold chain equipment failure on vehicle CV-02",
        device_faults=[{"device_id": "CV-02", "fault": "compressor_failure", "temp_c": 18.5}],
        signals=[SignalDef(
            id="sig-fridge", type="device_fault",
            text="Cold van CV-02 compressor failure, cabin temperature 18.5C",
            start_day=0,
        )],
    ),
    "bad_data": ScenarioDef(
        name="bad_data",
        description="Garbled stock report from SIM-PHC Hesaraghatta (H4)",
        signals=[SignalDef(
            id="sig-baddata", type="data_quality", facility="H4",
            text="H4 stock report contains OCR errors and mismatched batch numbers",
            start_day=0,
        )],
    ),
    "ilr_repaired": ScenarioDef(
        name="ilr_repaired",
        description="ILR repaired at SIM-PHC Hesaraghatta (H4)",
        signals=[SignalDef(
            id="sig-ilr", type="equipment_repair", facility="H4",
            text="Ice-Lined Refrigerator at H4 repaired and validated",
            start_day=0,
        )],
    ),
    "road_closure": ScenarioDef(
        name="road_closure",
        description="Road closure affecting routes through Yelahanka",
        route_closures=["H3-H1", "H1-H3"],
        signals=[SignalDef(
            id="sig-road", type="route_closure",
            text="Yelahanka main road closed for repair, ETA 5 days",
            start_day=0,
        )],
    ),
    "td_campaign": ScenarioDef(
        name="td_campaign",
        description="TD immunization campaign at SIM-DH Jayanagar (H1)",
        demand_multipliers=[
            DemandMult(facility="H1", drug_code="TD", multiplier=2.0, start_day=3, end_day=10),
        ],
        signals=[SignalDef(
            id="sig-td", type="campaign", facility="H1",
            drugs_affected=["TD"],
            text="Tetanus-diphtheria immunization campaign started at H1",
            start_day=3,
        )],
    ),
}

_active: list[ScenarioDef] = []


def activate(name: str) -> ScenarioDef:
    defn = SCENARIOS.get(name)
    if defn is None:
        raise ValueError(f"Unknown scenario: {name}")
    _active.append(defn)
    try:
        r = bus.get_redis()
        if defn.device_faults:
            existing = json.loads(r.get("sim:device_faults") or "[]")
            existing.extend(defn.device_faults)
            r.set("sim:device_faults", json.dumps(existing))
        if defn.route_closures:
            existing = json.loads(r.get("sim:route_closures") or "[]")
            existing.extend(defn.route_closures)
            r.set("sim:route_closures", json.dumps(existing))
        if defn.demand_multipliers:
            existing = json.loads(r.get("sim:demand_multipliers") or "[]")
            existing.extend([dm.model_dump() for dm in defn.demand_multipliers])
            r.set("sim:demand_multipliers", json.dumps(existing))
        if name == "ilr_repaired":
            r.delete("sim:device_faults")
    except Exception:
        pass
    return defn


def get_signals(day_index: int = 0) -> list[dict]:
    result = []
    for sc in _active:
        for sig in sc.signals:
            result.append({
                "id": sig.id,
                "type": sig.type,
                "facility": sig.facility,
                "drugs_affected": sig.drugs_affected,
                "text": sig.text,
                "start_day": sig.start_day,
                "params": {"facility": sig.facility, "drugs_affected": sig.drugs_affected},
                "fired_at": None,
            })
    return result


def get_multiplier(facility: str, drug_code: str, day_index: int) -> float:
    mult = 1.0
    for sc in _active:
        for dm in sc.demand_multipliers:
            if dm.facility == facility and dm.drug_code == drug_code:
                if dm.start_day <= day_index <= dm.end_day:
                    mult *= dm.multiplier
    return mult


def get_multipliers() -> list[dict]:
    result = []
    for sc in _active:
        for dm in sc.demand_multipliers:
            result.append(dm.model_dump())
    return result


def list_scenarios() -> list[dict]:
    return [{"name": s.name, "description": s.description} for s in SCENARIOS.values()]


def reset_scenarios():
    _active.clear()
    try:
        r = bus.get_redis()
        r.delete("sim:device_faults", "sim:route_closures", "sim:demand_multipliers")
    except Exception:
        pass
