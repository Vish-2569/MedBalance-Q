"""Facility zoning via Max-Cut (QAOA) and k-means comparison.

Live mode: nodes = facilities; scale mode: nodes = taluk super-nodes.
Edge weight = normalised transit cost (far = heavy → Max-Cut separates far groups).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from medbal_common.logging import get_logger

from .maxcut import maxcut_chain, MaxCutResult, _cut_value
from .snapshot import Snapshot

log = get_logger("optimizer.zoning")


@dataclass
class ZoneResult:
    zones: dict[str, int]  # facility_id → zone (0 or 1)
    zone_facilities: dict[int, list[str]]  # zone → [facility_ids]
    cut_value: float
    intra_zone_cost: float
    maxcut_result: MaxCutResult
    kmeans_comparison: dict[str, Any] | None = None


def build_facility_graph(snap: Snapshot) -> nx.Graph:
    """Build weighted graph: nodes=facilities, edge weight=normalised transit cost."""
    G = nx.Graph()
    for fid in snap.facilities:
        G.add_node(fid)

    costs = []
    for (src, dst), route in snap.routes.items():
        if src < dst:
            cost = route.cost_ambient_inr
            costs.append(cost)

    max_cost = max(costs) if costs else 1.0

    for (src, dst), route in snap.routes.items():
        if src < dst:
            w = route.cost_ambient_inr / max_cost
            G.add_edge(src, dst, weight=w)

    return G


def build_taluk_graph(snap: Snapshot, taluk_map: dict[str, str]) -> nx.Graph:
    """Build graph with taluk super-nodes; edge weight = avg inter-taluk transit cost."""
    G = nx.Graph()
    taluks = set(taluk_map.values())
    for t in taluks:
        G.add_node(t)

    edge_costs: dict[tuple[str, str], list[float]] = {}
    for (src, dst), route in snap.routes.items():
        t_src = taluk_map.get(src)
        t_dst = taluk_map.get(dst)
        if t_src and t_dst and t_src != t_dst:
            key = (min(t_src, t_dst), max(t_src, t_dst))
            edge_costs.setdefault(key, []).append(route.cost_ambient_inr)

    all_costs = [c for cs in edge_costs.values() for c in cs]
    max_cost = max(all_costs) if all_costs else 1.0

    for (t1, t2), costs in edge_costs.items():
        avg = sum(costs) / len(costs)
        G.add_edge(t1, t2, weight=avg / max_cost)

    return G


def _intra_zone_cost(snap: Snapshot, zones: dict[str, int]) -> float:
    """Total transit cost of routes within the same zone."""
    total = 0.0
    for (src, dst), route in snap.routes.items():
        if src < dst and zones.get(src) == zones.get(dst):
            total += route.cost_ambient_inr
    return total


def _kmeans_partition(snap: Snapshot, k: int = 2) -> dict[str, int]:
    """Simple k-means (k=2) on route-distance coordinates using 1D projection."""
    fac_ids = sorted(snap.facilities.keys())
    if len(fac_ids) <= k:
        return {f: i for i, f in enumerate(fac_ids)}

    avg_dist: dict[str, float] = {}
    for fid in fac_ids:
        dists = []
        for (src, dst), route in snap.routes.items():
            if src == fid:
                dists.append(route.distance_km)
        avg_dist[fid] = sum(dists) / len(dists) if dists else 0.0

    sorted_facs = sorted(fac_ids, key=lambda f: avg_dist[f])
    mid = len(sorted_facs) // 2
    partition = {}
    for i, f in enumerate(sorted_facs):
        partition[f] = 0 if i < mid else 1
    return partition


def zone_facilities(
    snap: Snapshot,
    *,
    mode: str = "live",
    taluk_map: dict[str, str] | None = None,
    depth: int = 1,
    shots: int = 1024,
) -> ZoneResult:
    """Partition facilities into 2 zones via Max-Cut.

    mode="live": one node per facility.
    mode="scale": one node per taluk (requires taluk_map).
    """
    if mode == "scale" and taluk_map:
        G = build_taluk_graph(snap, taluk_map)
        mc = maxcut_chain(G, depth=depth, shots=shots)
        zones: dict[str, int] = {}
        for fid, taluk in taluk_map.items():
            zones[fid] = mc.partition.get(taluk, 0)
    else:
        G = build_facility_graph(snap)
        mc = maxcut_chain(G, depth=depth, shots=shots)
        zones = {fid: mc.partition.get(fid, 0) for fid in snap.facilities}

    zone_facs: dict[int, list[str]] = {0: [], 1: []}
    for fid, z in zones.items():
        zone_facs.setdefault(z, []).append(fid)

    intra_cost = _intra_zone_cost(snap, zones)

    km_part = _kmeans_partition(snap)
    km_cut = _cut_value(G, km_part)
    km_intra = _intra_zone_cost(snap, km_part)

    return ZoneResult(
        zones=zones,
        zone_facilities=zone_facs,
        cut_value=mc.cut_value,
        intra_zone_cost=intra_cost,
        maxcut_result=mc,
        kmeans_comparison={
            "partition": km_part,
            "cut_value": km_cut,
            "intra_zone_cost": km_intra,
        },
    )
