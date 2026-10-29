from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError, create_model
from pydantic.fields import FieldInfo


def _schema_to_field(name: str, prop: dict[str, Any], required: bool) -> tuple[type, FieldInfo]:
    """Convert a JSON schema property to a Pydantic field type + FieldInfo."""
    t = prop.get("type", "string")
    default = ... if required else None

    if t == "string":
        return (str if required else str | None, FieldInfo(default=default))
    elif t == "integer":
        return (int if required else int | None, FieldInfo(default=default))
    elif t == "number":
        return (float if required else float | None, FieldInfo(default=default))
    elif t == "boolean":
        return (bool if required else bool | None, FieldInfo(default=default))
    elif t == "array":
        return (list if required else list | None, FieldInfo(default=default))
    elif t == "object":
        return (dict if required else dict | None, FieldInfo(default=default))
    else:
        return (Any, FieldInfo(default=default))


def make_model(schema: dict[str, Any]) -> type[BaseModel]:
    """Build a Pydantic model from a JSON schema dict."""
    props = schema.get("properties", {})
    required_keys = set(schema.get("required", []))
    fields: dict[str, Any] = {}
    for name, prop in props.items():
        fields[name] = _schema_to_field(name, prop, name in required_keys)
    return create_model("DynamicOutput", **fields)


def validate_output(output: Any, schema: dict[str, Any]) -> tuple[Any, str | None]:
    """Validate output against schema. Returns (validated_dict, error_or_None)."""
    if not isinstance(output, dict):
        return None, f"Expected dict, got {type(output).__name__}"
    try:
        model = make_model(schema)
        validated = model.model_validate(output)
        return validated.model_dump(), None
    except ValidationError as e:
        return None, str(e)
