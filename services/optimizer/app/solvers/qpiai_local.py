"""Tier 2: QpiAI Opt local solver (runs on-device, still needs API key)."""
from __future__ import annotations

import time

from medbal_common.logging import get_logger
from medbal_common.settings import settings

from .port import Sample, SolveResult

log = get_logger("solver.qpiai_local")


class QpiAIOptLocal:
    tier_name = "qpiai-local"

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
            from qpiai_opt.opt_solvers.local import (
                Client, LocalProvider, QUBOProblem,
            )

            token = settings.QPIAI_OPT_TOKEN
            if not settings._is_set(token):
                raise RuntimeError("QPIAI_OPT_TOKEN not set")

            client = Client(api_key=token)
            provider = LocalProvider(client=client)

            problem = QUBOProblem(
                problem_type="QUBO",
                num_variables=n_vars,
                matrix_format="upper",
                max_evaluations=500,
                sense="MIN",
                offset=offset,
                qubo_dict=Q,
            )

            result = provider.solve(
                problem,
                problem_class="QUBO",
                time_limit=timeout,
                num_reads=200,
                num_sweeps=1000,
            )

            x = _parse_assignment(result.variable_assignment, n_vars)
            elapsed = (time.perf_counter() - t0) * 1000

            return SolveResult(
                samples=[Sample(x=x, energy=result.objective + offset)],
                tier=self.tier_name,
                time_ms=elapsed,
                n_vars=n_vars,
                meta={
                    "solver_time_s": result.solver_time_s,
                    "objective": result.objective,
                    "execution_mode": result.execution_mode,
                },
            )

        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            log.warning("qpiai_local_failed", error=str(e))
            return SolveResult(
                samples=[],
                tier=self.tier_name,
                time_ms=elapsed,
                n_vars=n_vars,
                error=str(e),
            )


def _parse_assignment(
    va: dict[str, int | float], n_vars: int,
) -> dict[int, int]:
    x: dict[int, int] = {}
    for k, v in va.items():
        try:
            idx = int(k.replace("x", ""))
        except (ValueError, AttributeError):
            idx = int(k)
        x[idx] = int(round(v))
    for i in range(n_vars):
        x.setdefault(i, 0)
    return x
