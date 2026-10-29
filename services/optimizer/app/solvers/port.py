"""SolverPort protocol and result types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Sample:
    x: dict[int, int]
    energy: float


@dataclass
class SolveResult:
    samples: list[Sample]
    tier: str
    time_ms: float
    n_vars: int
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class SolverPort(Protocol):
    tier_name: str

    def solve(
        self,
        Q: dict[tuple[int, int], float],
        offset: float,
        n_vars: int,
        *,
        top_k: int = 5,
        timeout: float = 20.0,
    ) -> SolveResult: ...
