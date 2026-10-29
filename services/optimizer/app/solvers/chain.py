"""Tiered solver chain: try tiers in order, record evidence for every attempt."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from medbal_common.logging import get_logger

from .port import SolverPort, SolveResult
from .qpiai_platform import QpiAIOptPlatform
from .qpiai_local import QpiAIOptLocal
from .neal_sa import NealSA
from .greedy_descent import GreedyDescent

log = get_logger("solver.chain")

EVIDENCE_DIR = Path(__file__).resolve().parents[4] / "evidence" / "qpiai_runs"

DEFAULT_TIERS: list[SolverPort] = [
    QpiAIOptPlatform(),
    QpiAIOptLocal(),
    NealSA(),
    GreedyDescent(seed=42),
]


def solve_chain(
    Q: dict[tuple[int, int], float],
    offset: float,
    n_vars: int,
    *,
    top_k: int = 5,
    timeout: float = 20.0,
    preferred_tier: str | None = None,
    tiers: list[SolverPort] | None = None,
) -> SolveResult:
    """Try solver tiers in order. Record evidence for every attempt."""
    tier_list = tiers or DEFAULT_TIERS

    if preferred_tier:
        tier_list = sorted(
            tier_list,
            key=lambda t: 0 if t.tier_name == preferred_tier else 1,
        )

    attempts: list[dict[str, Any]] = []
    best_result: SolveResult | None = None

    for solver in tier_list:
        result = solver.solve(Q, offset, n_vars, top_k=top_k, timeout=timeout)

        attempt = {
            "tier": result.tier,
            "time_ms": round(result.time_ms, 2),
            "n_vars": result.n_vars,
            "samples_returned": len(result.samples),
            "energy": result.samples[0].energy if result.samples else None,
            "error": result.error,
        }
        attempts.append(attempt)

        if result.samples and result.error is None:
            best_result = result
            best_result.meta["attempts"] = attempts
            _write_evidence(Q, offset, n_vars, attempts, best_result)
            return best_result

        log.info(
            "tier_failed",
            tier=solver.tier_name,
            error=result.error,
            time_ms=round(result.time_ms, 1),
        )

    if best_result is None:
        best_result = SolveResult(
            samples=[], tier="none", time_ms=0, n_vars=n_vars,
            error="all tiers failed",
        )
    best_result.meta["attempts"] = attempts
    _write_evidence(Q, offset, n_vars, attempts, best_result)
    return best_result


def _write_evidence(
    Q: dict[tuple[int, int], float],
    offset: float,
    n_vars: int,
    attempts: list[dict[str, Any]],
    result: SolveResult,
) -> Path | None:
    try:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        q_hash = hashlib.sha256(
            json.dumps(
                {str(k): v for k, v in sorted(Q.items())}, sort_keys=True,
            ).encode()
        ).hexdigest()[:12]
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        fname = f"{ts}_{q_hash}.json"

        evidence = {
            "timestamp": ts,
            "n_vars": n_vars,
            "offset": offset,
            "q_hash": q_hash,
            "attempts": attempts,
            "winner": {
                "tier": result.tier,
                "energy": result.samples[0].energy if result.samples else None,
                "time_ms": round(result.time_ms, 2),
                "samples_count": len(result.samples),
            },
        }
        path = EVIDENCE_DIR / fname
        path.write_text(json.dumps(evidence, indent=2))
        log.info("evidence_written", path=str(path))
        return path
    except Exception as e:
        log.warning("evidence_write_failed", error=str(e))
        return None
