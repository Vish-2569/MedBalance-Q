"""Validate every fixture JSON against its OpenAPI schema."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
OPENAPI_DIR = ROOT / "openapi"
FIXTURES_DIR = ROOT / "fixtures"


def _load_spec(name: str) -> dict:
    path = OPENAPI_DIR / f"{name}.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_fixture(name: str):
    path = FIXTURES_DIR / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _resolver(spec: dict):
    """Build a jsonschema resolver that can handle $ref within components."""
    schemas = spec.get("components", {}).get("schemas", {})
    schema_store = {
        f"#/components/schemas/{name}": schema
        for name, schema in schemas.items()
    }
    return schemas, schema_store


def _resolve_ref(ref: str, schemas: dict) -> dict:
    """Resolve a $ref like '#/components/schemas/Facility' to the actual schema."""
    parts = ref.split("/")
    name = parts[-1]
    return schemas.get(name, {})


def _resolve_schema(schema: dict, schemas: dict) -> dict:
    """Recursively resolve $ref in a schema for validation."""
    if "$ref" in schema:
        resolved = _resolve_ref(schema["$ref"], schemas)
        return _resolve_schema(resolved, schemas)

    result = dict(schema)

    if "items" in result:
        result["items"] = _resolve_schema(result["items"], schemas)

    if "properties" in result:
        result["properties"] = {
            k: _resolve_schema(v, schemas)
            for k, v in result["properties"].items()
        }

    if "additionalProperties" in result and isinstance(result["additionalProperties"], dict):
        result["additionalProperties"] = _resolve_schema(result["additionalProperties"], schemas)

    return result


def _get_response_schema(spec: dict, path: str, method: str = "get") -> dict | None:
    """Extract the 200/201 response schema for a path+method from an OpenAPI spec."""
    path_item = spec.get("paths", {}).get(path, {})
    op = path_item.get(method, {})
    responses = op.get("responses", {})
    for code in ("200", "201"):
        resp = responses.get(code, {})
        content = resp.get("content", {})
        json_content = content.get("application/json", {})
        if "schema" in json_content:
            return json_content["schema"]
    return None


def _validate(data, schema: dict, schemas: dict):
    """Validate data against a schema, resolving $refs."""
    resolved = _resolve_schema(schema, schemas)
    validator = Draft202012Validator(resolved)
    errors = list(validator.iter_errors(data))
    if errors:
        msgs = [f"  - {e.message} at {list(e.absolute_path)}" for e in errors[:5]]
        raise AssertionError(
            f"Schema validation failed ({len(errors)} errors):\n" + "\n".join(msgs)
        )


# --- Mapping: (spec_file, openapi_path, method) -> fixture_file ---
VALIDATIONS = [
    ("core-api", "/facilities", "get", "facilities.json"),
    ("core-api", "/drugs", "get", "drugs.json"),
    ("core-api", "/routes", "get", "routes.json"),
    ("core-api", "/vehicles", "get", "vehicles.json"),
    ("core-api", "/lots", "get", "lots.json"),
    ("core-api", "/positions", "get", "positions.json"),
    ("core-api", "/snapshot", "get", "snapshot.json"),
    ("core-api", "/orders", "get", "orders.json"),
    ("core-api", "/audit/verify", "get", "audit-verify.json"),
    ("core-api", "/audit", "get", "audit.json"),
    ("forecast", "/forecast", "get", "forecasts.json"),
    ("forecast", "/forecast/backtest", "get", "backtest.json"),
    ("coldchain", "/status", "get", "coldchain-status.json"),
    ("sim-control", "/clock", "get", "clock.json"),
    ("sim-control", "/scenarios", "get", "scenarios.json"),
    ("sim-control", "/signals", "get", "signals.json"),
]


@pytest.mark.parametrize(
    "spec_name,path,method,fixture_file",
    VALIDATIONS,
    ids=[f"{s}:{p}" for s, p, _, _ in VALIDATIONS],
)
def test_fixture_matches_schema(spec_name, path, method, fixture_file):
    spec = _load_spec(spec_name)
    schemas, _ = _resolver(spec)
    schema = _get_response_schema(spec, path, method)
    assert schema is not None, f"No response schema for {method.upper()} {path} in {spec_name}"
    data = _load_fixture(fixture_file)
    _validate(data, schema, schemas)


def test_all_openapi_files_are_valid_yaml():
    """Every YAML file in openapi/ parses without error and has required keys."""
    for path in sorted(OPENAPI_DIR.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            spec = yaml.safe_load(f)
        assert "openapi" in spec, f"{path.name} missing 'openapi' key"
        assert "info" in spec, f"{path.name} missing 'info' key"
        assert "paths" in spec, f"{path.name} missing 'paths' key"


def test_all_fixtures_are_valid_json():
    """Every JSON file in fixtures/ parses without error."""
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data is not None, f"{path.name} loaded as None"


def test_plan_demo_structure():
    """The demo plan has exactly 6 orders, 1 insulin order with usable=28."""
    data = _load_fixture("plan-demo.json")
    assert "plan" in data
    assert "orders" in data
    assert "candidates" in data
    assert "regret" in data
    assert len(data["orders"]) == 6

    insulin = [o for o in data["orders"] if o["drug_code"] == "INSUL"]
    assert len(insulin) == 1
    assert insulin[0]["usable"] == 28
    assert insulin[0]["temperature_req"] == "cold_chain"


def test_facilities_consistent():
    """Facilities in fixtures/facilities.json match those in snapshot.json."""
    facilities = _load_fixture("facilities.json")
    snapshot = _load_fixture("snapshot.json")
    fac_ids = {f["id"] for f in facilities}
    snap_ids = {f["id"] for f in snapshot["facilities"]}
    assert fac_ids == snap_ids


def test_drugs_consistent():
    """Drugs in fixtures/drugs.json match those in snapshot.json."""
    drugs = _load_fixture("drugs.json")
    snapshot = _load_fixture("snapshot.json")
    drug_codes = {d["code"] for d in drugs}
    snap_codes = {d["code"] for d in snapshot["drugs"]}
    assert drug_codes == snap_codes


def test_orders_in_plan_match_standalone():
    """Orders in plan-demo.json match orders.json."""
    plan = _load_fixture("plan-demo.json")
    orders = _load_fixture("orders.json")
    plan_ids = {o["id"] for o in plan["orders"]}
    order_ids = {o["id"] for o in orders}
    assert plan_ids == order_ids


def test_events_md_exists():
    """events.md exists and mentions all expected streams."""
    path = ROOT / "events.md"
    assert path.exists(), "contracts/events.md not found"
    content = path.read_text(encoding="utf-8")
    expected_streams = [
        "report.received",
        "inventory.updated",
        "anomaly.flagged",
        "forecast.updated",
        "coldchain.alert",
        "plan.progress",
        "plan.completed",
        "plan.revised",
        "order.status",
        "custody.scanned",
    ]
    for stream in expected_streams:
        assert stream in content, f"Stream '{stream}' not documented in events.md"
