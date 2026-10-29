"""Tier 3: dwave-neal simulated annealing (no API key needed)."""
from __future__ import annotations

import time

from medbal_common.logging import get_logger

from .port import Sample, SolveResult
from ..qubo_builder import energy

log = get_logger("solver.neal_sa")


class NealSA:
    tier_name = "neal-sa"

    def __init__(self, num_reads: int = 200, num_sweeps: int = 1000):
        self._num_reads = num_reads
        self._num_sweeps = num_sweeps

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
        try:
            import neal  # type: ignore[import-untyped]

            bqm_Q: dict[tuple[int, int], float] = {}
            for (i, j), w in Q.items():
                if i == j:
                    bqm_Q[(i, i)] = bqm_Q.get((i, i), 0.0) + w
                else:
                    bqm_Q[(i, j)] = bqm_Q.get((i, j), 0.0) + w

            sampler = neal.SimulatedAnnealingSampler()
            response = sampler.sample_qubo(
                bqm_Q,
                num_reads=self._num_reads,
                num_sweeps=self._num_sweeps,
            )

            samples: list[Sample] = []
            for datum in response.data(fields=["sample", "energy"]):
                x = {i: int(datum.sample.get(i, 0)) for i in range(n_vars)}
                e = energy(Q, offset, x)
                samples.append(Sample(x=x, energy=e))

            samples.sort(key=lambda s: s.energy)
            samples = samples[:top_k]

            elapsed = (time.perf_counter() - t0) * 1000
            return SolveResult(
                samples=samples,
                tier=self.tier_name,
                time_ms=elapsed,
                n_vars=n_vars,
                meta={"num_reads": self._num_reads, "num_sweeps": self._num_sweeps},
            )

        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            log.warning("neal_sa_failed", error=str(e))
            return SolveResult(
                samples=[],
                tier=self.tier_name,
                time_ms=elapsed,
                n_vars=n_vars,
                error=str(e),
            )
