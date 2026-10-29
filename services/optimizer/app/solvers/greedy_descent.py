"""Tier 4: greedy bit-flip descent from random starts. Always works."""
from __future__ import annotations

import random
import time

from .port import Sample, SolveResult
from ..qubo_builder import energy


class GreedyDescent:
    tier_name = "greedy-descent"

    def __init__(self, restarts: int = 50, seed: int | None = None):
        self._restarts = restarts
        self._seed = seed

    def solve(
        self,
        Q: dict[tuple[int, int], float],
        offset: float,
        n_vars: int,
        *,
        top_k: int = 5,
        timeout: float = 10.0,
    ) -> SolveResult:
        t0 = time.perf_counter()
        rng = random.Random(self._seed)
        deadline = t0 + timeout

        all_samples: list[Sample] = []

        for _ in range(self._restarts):
            if time.perf_counter() > deadline:
                break
            x = {i: rng.randint(0, 1) for i in range(n_vars)}
            x = _descend(Q, offset, n_vars, x, deadline)
            e = energy(Q, offset, x)
            all_samples.append(Sample(x=dict(x), energy=e))

        all_samples.sort(key=lambda s: s.energy)
        unique: list[Sample] = []
        seen: set[tuple[int, ...]] = set()
        for s in all_samples:
            key = tuple(s.x[i] for i in range(n_vars))
            if key not in seen:
                seen.add(key)
                unique.append(s)
                if len(unique) >= top_k:
                    break

        elapsed = (time.perf_counter() - t0) * 1000
        return SolveResult(
            samples=unique,
            tier=self.tier_name,
            time_ms=elapsed,
            n_vars=n_vars,
            meta={"restarts": self._restarts},
        )


def _descend(
    Q: dict[tuple[int, int], float],
    offset: float,
    n_vars: int,
    x: dict[int, int],
    deadline: float,
) -> dict[int, int]:
    improved = True
    while improved:
        if time.perf_counter() > deadline:
            break
        improved = False
        cur_e = energy(Q, offset, x)
        for i in range(n_vars):
            x[i] ^= 1
            new_e = energy(Q, offset, x)
            if new_e < cur_e:
                cur_e = new_e
                improved = True
            else:
                x[i] ^= 1
    return x
