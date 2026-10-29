"""Drug name grounding via exact + fuzzy matching against the master drug list."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from rapidfuzz.fuzz import token_sort_ratio


@dataclass
class GroundingResult:
    drug_code: str | None
    drug_name: str | None
    score: int
    method: str  # exact | fuzzy | unknown


_THRESHOLD = 70

_index: dict[str, tuple[str, str]] | None = None


def _find_drugs_yaml() -> Path | None:
    candidates = [
        Path(__file__).resolve().parents[3] / "data" / "seed" / "drugs.yaml",
        Path("/app/data/seed/drugs.yaml"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _build_index() -> dict[str, tuple[str, str]]:
    """Map lowercased name/alias → (drug_code, canonical_name)."""
    path = _find_drugs_yaml()
    if path is None:
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    idx: dict[str, tuple[str, str]] = {}
    for drug in data.get("drugs", []):
        code = drug["code"]
        name = drug["name"]
        idx[name.lower()] = (code, name)
        idx[code.lower()] = (code, name)
        for alias_entry in drug.get("aliases", []):
            alias = alias_entry["alias"]
            idx[alias.lower()] = (code, name)
    return idx


def _get_index() -> dict[str, tuple[str, str]]:
    global _index
    if _index is None:
        _index = _build_index()
    return _index


def reload_index() -> None:
    """Force rebuild — useful after tests swap the yaml path."""
    global _index
    _index = None


def ground_drug(raw_name: str) -> GroundingResult:
    """Match a raw drug name to the master list."""
    idx = _get_index()
    if not idx:
        return GroundingResult(drug_code=None, drug_name=None, score=0, method="unknown")

    key = raw_name.strip().lower()
    if not key:
        return GroundingResult(drug_code=None, drug_name=None, score=0, method="unknown")

    if key in idx:
        code, name = idx[key]
        return GroundingResult(drug_code=code, drug_name=name, score=100, method="exact")

    best_score = 0.0
    best_match: tuple[str, str] | None = None
    for indexed_name, (code, name) in idx.items():
        score = token_sort_ratio(key, indexed_name)
        if score > best_score:
            best_score = score
            best_match = (code, name)

    if best_score >= _THRESHOLD and best_match is not None:
        return GroundingResult(
            drug_code=best_match[0],
            drug_name=best_match[1],
            score=int(best_score),
            method="fuzzy",
        )

    return GroundingResult(drug_code=None, drug_name=None, score=0, method="unknown")


def ground_drugs_batch(items: list) -> list:
    """Enrich ExtractionItem objects with grounded drug_code."""
    for item in items:
        raw = getattr(item, "drug_name_raw", "") or ""
        result = ground_drug(raw)
        if result.drug_code and not getattr(item, "drug_code", None):
            item.drug_code = result.drug_code
        item.grounding_score = result.score
        item.grounding_method = result.method
    return items
