"""In-memory forecast store with persistence hooks.

Stores forecast rows keyed by (facility_id, drug_code).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any


@dataclass
class ForecastRow:
    facility_id: str
    drug_code: str
    horizon_days: int
    daily_rate: float
    method: str
    confidence: float
    context_multiplier: float
    adjusted_rate: float
    p10: float = 0.0
    p90: float = 0.0
    signal_ids: list[str] = field(default_factory=list)
    reasoning: str = ""
    computed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "facility_id": self.facility_id,
            "drug_code": self.drug_code,
            "horizon_days": self.horizon_days,
            "daily_rate": self.daily_rate,
            "method": self.method,
            "confidence": self.confidence,
            "context_multiplier": self.context_multiplier,
            "adjusted_rate": self.adjusted_rate,
            "p10": self.p10,
            "p90": self.p90,
            "signal_ids": self.signal_ids,
            "reasoning": self.reasoning,
            "computed_at": self.computed_at,
        }


class ForecastStore:
    """In-memory store for forecast rows."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], ForecastRow] = {}
        self._history: list[ForecastRow] = []

    def upsert(self, row: ForecastRow) -> None:
        key = (row.facility_id, row.drug_code)
        self._rows[key] = row
        self._history.append(row)

    def get(self, facility_id: str, drug_code: str) -> ForecastRow | None:
        return self._rows.get((facility_id, drug_code))

    def list_all(
        self,
        facility: str | None = None,
        drug: str | None = None,
    ) -> list[ForecastRow]:
        rows = list(self._rows.values())
        if facility:
            rows = [r for r in rows if r.facility_id == facility]
        if drug:
            rows = [r for r in rows if r.drug_code == drug]
        return rows

    def history(self) -> list[ForecastRow]:
        return list(self._history)

    def clear(self) -> None:
        self._rows.clear()
        self._history.clear()


# Module-level singleton
forecast_store = ForecastStore()
