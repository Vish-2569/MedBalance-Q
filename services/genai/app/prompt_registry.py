from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Template

_DEFAULT_DIR = Path(__file__).resolve().parents[1] / "prompts"
_DOCKER_DIR = Path("/app/prompts")
PROMPTS_DIR = _DOCKER_DIR if _DOCKER_DIR.exists() else _DEFAULT_DIR


@dataclass(frozen=True)
class PromptSpec:
    id: str
    version: int
    system: str
    user_template: str
    json_schema: dict[str, Any] | None = None
    model: str = "fast"
    temperature: float = 0.0
    max_tokens: int = 1024
    tools: list[dict[str, Any]] | None = None

    @property
    def ref(self) -> str:
        return f"{self.id}@v{self.version}"

    def render_user(self, input_data: dict[str, Any]) -> str:
        return Template(self.user_template).render(**input_data)


_registry: dict[str, PromptSpec] = {}
_mtimes: dict[str, float] = {}


def _load_file(path: Path) -> PromptSpec | None:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        return PromptSpec(
            id=raw["id"],
            version=int(raw["version"]),
            system=raw.get("system", ""),
            user_template=raw.get("user_template", ""),
            json_schema=raw.get("json_schema"),
            model=raw.get("model", "fast"),
            temperature=float(raw.get("temperature", 0.0)),
            max_tokens=int(raw.get("max_tokens", 1024)),
            tools=raw.get("tools"),
        )
    except Exception:
        return None


def load_all(directory: Path | None = None) -> None:
    d = directory or PROMPTS_DIR
    if not d.exists():
        return
    _registry.clear()
    _mtimes.clear()
    for p in sorted(d.glob("*_v*.yaml")):
        spec = _load_file(p)
        if spec:
            _registry[spec.ref] = spec
            _mtimes[spec.ref] = p.stat().st_mtime


def _hot_reload(directory: Path | None = None) -> None:
    d = directory or PROMPTS_DIR
    if not d.exists():
        return
    for p in sorted(d.glob("*_v*.yaml")):
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        spec = _load_file(p)
        if not spec:
            continue
        if spec.ref not in _mtimes or _mtimes[spec.ref] < mtime:
            _registry[spec.ref] = spec
            _mtimes[spec.ref] = mtime


def get(prompt_id: str, version: int, *, reload: bool = False) -> PromptSpec | None:
    ref = f"{prompt_id}@v{version}"
    if reload or os.environ.get("GENAI_HOT_RELOAD", "").lower() in ("1", "true"):
        _hot_reload()
    return _registry.get(ref)


def list_prompts() -> list[str]:
    return sorted(_registry.keys())
