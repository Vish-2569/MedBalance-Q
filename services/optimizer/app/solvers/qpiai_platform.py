"""Tier 1: QpiAI Opt cloud platform solver."""
from __future__ import annotations

import time
from typing import Any

from medbal_common.logging import get_logger
from medbal_common.settings import settings

from .port import Sample, SolveResult

log = get_logger("solver.qpiai_platform")


class QpiAIOptPlatform:
    tier_name = "qpiai-platform"

    def solve(
        self,
        Q: dict[tuple[int, int], float],
        offset: float,
        n_vars: int,
        *,
        top_k: int = 5,
        timeout: float = 20.0,
    ) -> SolveResult:
        t0 = time.perf_counter()
        try:
            from qpiai_opt.opt_solvers.local import Client, QUBOProblem

            if not settings.has_qpiai_opt():
                raise RuntimeError("QPIAI_OPT_URL or QPIAI_OPT_TOKEN not set")

            client = Client(
                api_key=settings.QPIAI_OPT_TOKEN,
                base_url=settings.QPIAI_OPT_URL,
                timeout=timeout,
            )

            problem = QUBOProblem(
                problem_type="QUBO",
                num_variables=n_vars,
                matrix_format="upper",
                max_evaluations=1000,
                sense="MIN",
                offset=offset,
                qubo_dict=Q,
            )

            created = client.create_problem(problem.model_dump(), timeout=timeout)
            submission = client.submit_job(created.id, timeout=timeout)
            job = client.wait_for_job(
                submission.job_id, timeout=timeout, poll_interval=1.0,
            )
            result = client.extract_result(job, timeout=timeout)

            x = _parse_assignment(result.variable_assignment, n_vars)
            elapsed = (time.perf_counter() - t0) * 1000

            return SolveResult(
                samples=[Sample(x=x, energy=result.objective + offset)],
                tier=self.tier_name,
                time_ms=elapsed,
                n_vars=n_vars,
                meta={
                    "job_id": result.job_id,
                    "solver_time_s": result.solver_time_s,
                    "objective": result.objective,
                },
            )

        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            log.warning("qpiai_platform_failed", error=str(e))
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
