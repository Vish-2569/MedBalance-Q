"""Max-Cut solver with tiered backends for facility zoning.

Tiers: QCloud simulator → QSV-Local → exact brute force (n≤16) → NetworkX greedy.
Evidence JSON logged for every attempt.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import networkx as nx

from medbal_common.logging import get_logger
from medbal_common.settings import settings

log = get_logger("optimizer.maxcut")

_module_path = Path(__file__).resolve()
_project_root = _module_path.parents[3] if len(_module_path.parents) > 3 else _module_path.parents[1]
EVIDENCE_DIR = _project_root / "evidence" / "qpiai_runs"


@dataclass
class MaxCutResult:
    partition: dict[str, int]  # node → 0 or 1
    cut_value: float
    tier: str
    time_ms: float
    depth: int  # QAOA layers (0 for non-QAOA)
    shots: int
    approx_ratio: float  # cut / exact (NaN if exact unknown)
    meta: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class MaxCutPort(Protocol):
    tier_name: str
    def solve(self, G: nx.Graph, *, depth: int, shots: int) -> MaxCutResult: ...


# ── QAOA circuit builder ─────────────────────────────────────────────────────

def _build_qaoa_circuit(G: nx.Graph, gamma: float, beta: float, depth: int):
    """Build a QAOA circuit for Max-Cut using qpiai_quantum SDK."""
    from qpiai_quantum import Circuit, QuantumRegister, ClassicalRegister

    n = G.number_of_nodes()
    nodes = sorted(G.nodes())
    node_to_idx = {nd: i for i, nd in enumerate(nodes)}

    qr = QuantumRegister(n)
    cr = ClassicalRegister(n)
    circuit = Circuit(qr, cr)

    for i in range(n):
        circuit.h(i)

    for _layer in range(depth):
        for u, v, data in G.edges(data=True):
            w = data.get("weight", 1.0)
            qi, qj = node_to_idx[u], node_to_idx[v]
            circuit.rzz(qi, qj, gamma * w)

        for i in range(n):
            circuit.rx(i, 2 * beta)

    circuit.measure_all()
    return circuit, nodes


def _cut_value(G: nx.Graph, partition: dict[Any, int]) -> float:
    total = 0.0
    for u, v, data in G.edges(data=True):
        w = data.get("weight", 1.0)
        if partition.get(u, 0) != partition.get(v, 0):
            total += w
    return total


def _best_from_counts(
    G: nx.Graph, counts: dict[str, int], nodes: list
) -> tuple[dict[str, int], float]:
    """Pick the bitstring with the highest cut value from measurement counts."""
    best_partition: dict[str, int] = {}
    best_cut = -1.0

    top_bitstrings = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:20]

    for bitstring, _count in top_bitstrings:
        partition = {}
        for i, node in enumerate(nodes):
            bit_idx = len(bitstring) - 1 - i
            if 0 <= bit_idx < len(bitstring):
                partition[node] = int(bitstring[bit_idx])
            else:
                partition[node] = 0
        cv = _cut_value(G, partition)
        if cv > best_cut:
            best_cut = cv
            best_partition = partition

    return best_partition, best_cut


# ── Tier 1: QCloud Simulator ────────────────────────────────────────────────

class QCloudSimulator:
    tier_name = "qcloud-simulator"

    def solve(self, G: nx.Graph, *, depth: int = 1, shots: int = 1024) -> MaxCutResult:
        t0 = time.perf_counter()
        try:
            if not settings.has_qcloud():
                raise RuntimeError("QPIAI_QCLOUD_API_KEY not set")

            from qpiai_quantum import QpiAIQuantumAuth
            QpiAIQuantumAuth.login(settings.QPIAI_QCLOUD_API_KEY)
            QpiAIQuantumAuth.verify_api_key()

            best_p, best_cut = {}, -1.0
            for gamma in [0.5, 1.0, 1.5]:
                for beta in [0.3, 0.6, 1.0]:
                    circ, nodes = _build_qaoa_circuit(G, gamma, beta, depth)
                    result = circ.run(
                        shots=shots,
                        experiment_name="QAOA_MaxCut",
                        device_name=settings.QPIAI_QCLOUD_BACKEND,
                    )
                    counts = result.get_counts() or {}
                    p, cv = _best_from_counts(G, counts, nodes)
                    if cv > best_cut:
                        best_cut = cv
                        best_p = p

            ms = (time.perf_counter() - t0) * 1000
            return MaxCutResult(
                partition=best_p, cut_value=best_cut, tier=self.tier_name,
                time_ms=ms, depth=depth, shots=shots, approx_ratio=float("nan"),
            )
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            return MaxCutResult(
                partition={}, cut_value=0, tier=self.tier_name,
                time_ms=ms, depth=depth, shots=shots, approx_ratio=0,
                error=str(e),
            )


# ── Tier 2: QSV-Local ───────────────────────────────────────────────────────

class QSVLocal:
    tier_name = "qsv-local"

    def solve(self, G: nx.Graph, *, depth: int = 1, shots: int = 1024) -> MaxCutResult:
        t0 = time.perf_counter()
        try:
            from qpiai_quantum import Circuit, QuantumRegister, ClassicalRegister

            best_p, best_cut = {}, -1.0
            for gamma in [0.5, 1.0, 1.5]:
                for beta in [0.3, 0.6, 1.0]:
                    circ, nodes = _build_qaoa_circuit(G, gamma, beta, depth)
                    result = circ.run(
                        shots=shots,
                        experiment_name="QAOA_MaxCut_Local",
                        device_name="QpiAI-QSV-Local",
                    )
                    counts = result.get_counts() or {}
                    p, cv = _best_from_counts(G, counts, nodes)
                    if cv > best_cut:
                        best_cut = cv
                        best_p = p

            ms = (time.perf_counter() - t0) * 1000
            return MaxCutResult(
                partition=best_p, cut_value=best_cut, tier=self.tier_name,
                time_ms=ms, depth=depth, shots=shots, approx_ratio=float("nan"),
            )
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            return MaxCutResult(
                partition={}, cut_value=0, tier=self.tier_name,
                time_ms=ms, depth=depth, shots=shots, approx_ratio=0,
                error=str(e),
            )


# ── Tier 3: Exact Brute Force (n ≤ 16) ──────────────────────────────────────

class ExactBruteForce:
    tier_name = "exact-brute-force"
    MAX_N = 16

    def solve(self, G: nx.Graph, *, depth: int = 0, shots: int = 0) -> MaxCutResult:
        t0 = time.perf_counter()
        n = G.number_of_nodes()
        if n > self.MAX_N:
            ms = (time.perf_counter() - t0) * 1000
            return MaxCutResult(
                partition={}, cut_value=0, tier=self.tier_name,
                time_ms=ms, depth=0, shots=0, approx_ratio=0,
                error=f"Too many nodes ({n} > {self.MAX_N})",
            )

        nodes = sorted(G.nodes())
        best_cut = -1.0
        best_bits = 0

        for bits in range(1 << n):
            partition = {nodes[i]: (bits >> i) & 1 for i in range(n)}
            cv = _cut_value(G, partition)
            if cv > best_cut:
                best_cut = cv
                best_bits = bits

        partition = {nodes[i]: (best_bits >> i) & 1 for i in range(n)}
        ms = (time.perf_counter() - t0) * 1000
        return MaxCutResult(
            partition=partition, cut_value=best_cut, tier=self.tier_name,
            time_ms=ms, depth=0, shots=0, approx_ratio=1.0,
        )


# ── Tier 4: NetworkX Greedy ──────────────────────────────────────────────────

class NetworkXGreedy:
    tier_name = "networkx-greedy"

    def solve(self, G: nx.Graph, *, depth: int = 0, shots: int = 0) -> MaxCutResult:
        t0 = time.perf_counter()
        try:
            # one_exchange returns (cut_value, (set0, set1))
            cv, (s0, s1) = nx.approximation.one_exchange(G, weight="weight")
            nodes = sorted(G.nodes())
            partition = {nd: (0 if nd in s0 else 1) for nd in nodes}

            ms = (time.perf_counter() - t0) * 1000
            return MaxCutResult(
                partition=partition, cut_value=cv, tier=self.tier_name,
                time_ms=ms, depth=0, shots=0, approx_ratio=float("nan"),
            )
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            return MaxCutResult(
                partition={}, cut_value=0, tier=self.tier_name,
                time_ms=ms, depth=0, shots=0, approx_ratio=0,
                error=str(e),
            )


# ── Chain ────────────────────────────────────────────────────────────────────

DEFAULT_MAXCUT_TIERS: list[MaxCutPort] = [
    QCloudSimulator(),
    QSVLocal(),
    ExactBruteForce(),
    NetworkXGreedy(),
]


def maxcut_chain(
    G: nx.Graph,
    *,
    depth: int = 1,
    shots: int = 1024,
    tiers: list[MaxCutPort] | None = None,
) -> MaxCutResult:
    """Try Max-Cut tiers in order. Record evidence for every attempt."""
    print("[QPI AI QCLOUD] Running QAOA Max-Cut zoning...")
    print(f"[QPI AI QCLOUD] Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"[QPI AI QCLOUD] Depth: {depth}, Shots: {shots}")
    log.info("maxcut_chain_start", nodes=G.number_of_nodes(), edges=G.number_of_edges(), depth=depth, shots=shots)

    tier_list = tiers or DEFAULT_MAXCUT_TIERS
    attempts: list[dict[str, Any]] = []
    best: MaxCutResult | None = None

    exact_cut: float | None = None
    n = G.number_of_nodes()
    if n <= ExactBruteForce.MAX_N:
        exact_solver = ExactBruteForce()
        exact_result = exact_solver.solve(G)
        exact_cut = exact_result.cut_value

    for solver in tier_list:
        print(f"[QPI AI QCLOUD] Trying tier: {solver.tier_name}...")
        log.info("maxcut_tier_trying", tier=solver.tier_name)
        result = solver.solve(G, depth=depth, shots=shots)

        if exact_cut and exact_cut > 0 and result.cut_value > 0:
            result.approx_ratio = result.cut_value / exact_cut

        attempt = {
            "tier": result.tier,
            "time_ms": round(result.time_ms, 2),
            "cut_value": result.cut_value,
            "approx_ratio": round(result.approx_ratio, 4) if not math.isnan(result.approx_ratio) else None,
            "error": result.error,
        }
        attempts.append(attempt)

        if result.error is None and result.cut_value >= 0:
            ratio = result.approx_ratio if not math.isnan(result.approx_ratio) else 0.0
            print(f"[QPI AI QCLOUD] OK Tier: {solver.tier_name}")
            print(f"[QPI AI QCLOUD] Best cut value: {result.cut_value}, Approx ratio: {ratio:.3f}")
            log.info("maxcut_tier_succeeded", tier=solver.tier_name, cut_value=result.cut_value, approx_ratio=round(ratio, 4))
            best = result
            best.meta["attempts"] = attempts
            best.meta["exact_cut"] = exact_cut
            _write_maxcut_evidence(G, attempts, best)
            return best

        print(f"[QPI AI QCLOUD] SKIP {solver.tier_name} skipped - {result.error}")
        log.info("maxcut_tier_failed", tier=solver.tier_name, error=result.error)

    if best is None:
        best = MaxCutResult(
            partition={}, cut_value=0, tier="none", time_ms=0,
            depth=depth, shots=shots, approx_ratio=0,
            error="all tiers failed",
        )
    best.meta["attempts"] = attempts
    _write_maxcut_evidence(G, attempts, best)
    return best


def _write_maxcut_evidence(
    G: nx.Graph,
    attempts: list[dict[str, Any]],
    result: MaxCutResult,
) -> Path | None:
    try:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        g_hash = hashlib.sha256(
            json.dumps(sorted(G.edges(data=True), key=str)).encode()
        ).hexdigest()[:12]
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        fname = f"{ts}_mc_{g_hash}.json"

        evidence = {
            "timestamp": ts,
            "type": "maxcut",
            "n_nodes": G.number_of_nodes(),
            "n_edges": G.number_of_edges(),
            "graph_hash": g_hash,
            "attempts": attempts,
            "winner": {
                "tier": result.tier,
                "cut_value": result.cut_value,
                "approx_ratio": round(result.approx_ratio, 4) if not math.isnan(result.approx_ratio) else None,
                "time_ms": round(result.time_ms, 2),
                "depth": result.depth,
                "shots": result.shots,
            },
        }
        path = EVIDENCE_DIR / fname
        path.write_text(json.dumps(evidence, indent=2))
        return path
    except Exception as e:
        log.warning("maxcut_evidence_write_failed", error=str(e))
        return None
