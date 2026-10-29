"""Optimizer API routes."""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from medbal_common.logging import get_logger
from medbal_common.settings import settings
from medbal_common import bus

from .baselines import greedy_f4, greedy_phone_call, TransferOrder
from .candidates import generate_candidates, Candidate
from .decompose import decomposed_solve
from .metrics import compute_metrics
from .milp import solve_milp
from .positions import compute_all_positions
from .regret import compute_regret_from_vars
from .replan import set_live_plan
from .scale import generate_scale_snapshot
from .snapshot import build_snapshot, Snapshot
from .qubo_builder import build_qubo, QUBOConfig, QUBOResult, energy, term_breakdown
from .solvers import solve_chain, SolveResult
from .solvers.greedy_descent import GreedyDescent
from .validator import apply_plan, ValidatedOrder
from .whatif import run_whatif
from .whynot import compute_whynot
from .zoning import zone_facilities

log = get_logger("optimizer.router")

router = APIRouter()

CORE_API_URL = "http://core-api:8001"

# In-memory cache for benchmark lookups (plan_id → snapshot + taluk_map)
_PLAN_SNAPSHOTS: dict[str, tuple[Snapshot, dict[str, str] | None]] = {}
_PLAN_CANDIDATES: dict[str, list[Candidate]] = {}
_PLAN_ORDERS: dict[str, list[TransferOrder]] = {}
_PLAN_QUBO: dict[str, QUBOResult] = {}
_PLAN_SOLVE: dict[str, SolveResult] = {}
_PLAN_METRICS: dict[str, Any] = {}
_LATEST_PLAN_ID: str | None = None


class PlanRequest(BaseModel):
    mode: str = "live"
    solver: str = "qubo"
    scale: int | None = None
    overrides: dict[str, Any] | None = None


def _load_snapshot(mode: str) -> Snapshot:
    if settings.USE_FIXTURES:
        from medbal_common.fixtures import CONTRACTS_DIR
        raw = json.loads((CONTRACTS_DIR / "snapshot.json").read_text())
        return build_snapshot(raw, today=__import__("datetime").date(2026, 11, 1))

    resp = httpx.get(f"{CORE_API_URL}/snapshot", timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    today_str = data.get("today")
    if today_str:
        today = __import__("datetime").date.fromisoformat(today_str[:10])
    else:
        from medbal_common.clock import today as clock_today
        today = clock_today()
    return build_snapshot(data, today=today)


def _publish_progress(plan_id: str, stage: str, detail: str = "") -> None:
    try:
        bus.publish("plan.progress", {
            "plan_id": plan_id,
            "stage": stage,
            "detail": detail,
        })
    except Exception:
        pass


def _persist_plan(plan_payload: dict[str, Any]) -> str:
    if settings.USE_FIXTURES:
        return plan_payload["plan"]["id"]
    try:
        resp = httpx.post(
            f"{CORE_API_URL}/plans",
            json=plan_payload,
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json().get("plan_id", plan_payload["plan"]["id"])
    except Exception as e:
        log.warning("persist_failed", error=str(e))
        return plan_payload["plan"]["id"]


def _qubo_config_from_overrides(overrides: dict[str, Any] | None) -> QUBOConfig:
    if not overrides:
        return QUBOConfig()
    return QUBOConfig(
        p1=overrides.get("p1", 2.0),
        p2=overrides.get("p2", 1.5),
        p3=overrides.get("p3", 1.0),
        gamma=overrides.get("gamma"),
    )


def _run_qubo_pipeline(
    snap: Snapshot,
    candidates: list[Candidate],
    plan_id: str,
    overrides: dict[str, Any] | None,
) -> tuple[list[TransferOrder], dict[str, Any]]:
    """Run QUBO build → solve → validate → convert to TransferOrders."""
    config = _qubo_config_from_overrides(overrides)

    ven_priority = {
        code: drug.ven_priority for code, drug in snap.drugs.items()
    }
    shortages = {
        (fac_id, dc): pos.shortage
        for (fac_id, dc), pos in snap.positions.items()
        if pos.shortage > 0
    }

    print("[QPI AI OPT] Building QUBO matrix...")
    log.info("qubo_build_start")
    _publish_progress(plan_id, "qubo_build", "Building QUBO matrix")
    qubo_result = build_qubo(candidates, ven_priority, shortages, config)

    print(f"[QPI AI OPT] QUBO built: {qubo_result.num_variables} variables, {len(qubo_result.Q)} terms")
    print("[QPI AI OPT] Applying Capacity & Chemistry Penalties...")
    log.info("qubo_built", n_vars=qubo_result.num_variables, n_terms=len(qubo_result.Q))

    if qubo_result.num_variables == 0:
        print("[QPI AI OPT] QUBO empty — no variables to solve")
        return [], {"solver_tier": "qubo-empty", "energy": None, "n_vars": 0}

    _publish_progress(plan_id, "solve", f"Solving QUBO ({qubo_result.num_variables} vars)")
    print(f"[QPI AI OPT] Solving via solver chain ({qubo_result.num_variables} vars)...")
    log.info("solve_start", n_vars=qubo_result.num_variables)
    solve_result = solve_chain(
        qubo_result.Q, qubo_result.offset, qubo_result.num_variables,
        top_k=5, timeout=settings.QPIAI_TIMEOUT_S,
    )

    if not solve_result.samples:
        print(f"[QPI AI OPT] Solver Status: FAILED. Error: {solve_result.error}")
        log.warning("qubo_no_solution", error=solve_result.error)
        return [], {
            "solver_tier": solve_result.tier,
            "energy": None,
            "error": solve_result.error,
        }

    best = solve_result.samples[0]
    print(f"[QPI AI OPT] Solver Status: SUCCESS. Energy: {best.energy:.4f}")
    log.info("solve_complete", tier=solve_result.tier, energy=round(best.energy, 4), time_ms=round(solve_result.time_ms, 2))

    selected_pairs: list[tuple[int, Candidate]] = []
    for var_idx, val in best.x.items():
        if val == 1 and var_idx < len(qubo_result.variables):
            ci = qubo_result.variables[var_idx]
            selected_pairs.append((ci, candidates[ci]))

    _publish_progress(plan_id, "validate", "Validating solution")
    print(f"[QPI AI OPT] Validating {len(selected_pairs)} orders against FEFO snapshot...")
    log.info("validate_start", n_selected=len(selected_pairs))
    val_result = apply_plan(snap, selected_pairs)

    print(f"[QPI AI OPT] Validation: {'PASS' if not val_result.violations else 'REPAIRED'} — {len(val_result.violations)} violations, {val_result.trimmed_count} repairs")
    log.info("validate_complete", violations=len(val_result.violations), trimmed=val_result.trimmed_count, dropped=val_result.dropped_count)

    orders: list[TransferOrder] = []
    term_breakdowns: list[dict[str, Any]] = []
    for vo in val_result.orders:
        if vo.dropped:
            continue
        drug = snap.drugs.get(vo.drug_code)
        orders.append(TransferOrder(
            id=f"ORD-Q-{len(orders)+1:03d}",
            src_facility_id=vo.src_facility_id,
            dst_facility_id=vo.dst_facility_id,
            drug_code=vo.drug_code,
            drug_name=drug.name if drug else vo.drug_code,
            batch_no=vo.batch_no,
            qty=vo.qty,
            usable=vo.usable,
            score=round(best.energy, 4),
            temperature_req="cold_chain" if (drug and drug.cold_chain) else "ambient",
        ))

    print(f"[QPI AI OPT] Orders generated: {len(orders)}, Violations: {len(val_result.violations)}")
    log.info("orders_generated", count=len(orders), violations=len(val_result.violations))

    bd = term_breakdown(
        qubo_result.Q, qubo_result.offset, best.x,
        candidates, qubo_result.variables,
        ven_priority, shortages, qubo_result.config_used, qubo_result.norm_factor,
    )

    # Build var→order_id mapping for regret
    var_to_order: dict[int, str] = {}
    order_idx = 0
    for var_idx, val in best.x.items():
        if val == 1 and var_idx < len(qubo_result.variables):
            ci = qubo_result.variables[var_idx]
            for vo in val_result.orders:
                if not vo.dropped and vo.candidate_index == ci:
                    if order_idx < len(orders):
                        var_to_order[var_idx] = orders[order_idx].id
                    break
            order_idx += 1

    regret_ledger = []
    try:
        regret_ledger = compute_regret_from_vars(
            var_to_order, candidates, qubo_result, solve_result, ven_priority,
        )
    except Exception as exc:
        log.warning("regret_computation_failed", error=str(exc))

    # Cache QUBO and solve results
    _PLAN_QUBO[plan_id] = qubo_result
    _PLAN_SOLVE[plan_id] = solve_result

    solver_meta = {
        "solver_tier": solve_result.tier,
        "energy": best.energy,
        "n_vars": qubo_result.num_variables,
        "time_ms": round(solve_result.time_ms, 2),
        "violations": len(val_result.violations),
        "trimmed": val_result.trimmed_count,
        "dropped": val_result.dropped_count,
        "term_breakdown": bd,
        "config": {
            "p1": config.p1, "p2": config.p2,
            "p3": config.p3, "gamma": qubo_result.config_used.gamma,
        },
        "attempts": solve_result.meta.get("attempts", []),
        "regret": [r.to_dict() for r in regret_ledger],
    }

    return orders, solver_meta


@router.post("/plan/run")
async def run_plan(req: PlanRequest):
    plan_id = f"plan-{uuid.uuid4().hex[:8]}"

    print("=" * 60)
    print("[QPI AI OPT] Received plan request from UI...")
    log.info("plan_request_received", plan_id=plan_id, mode=req.mode, solver=req.solver)

    _publish_progress(plan_id, "snapshot", "Fetching district snapshot")

    if req.mode == "eval" and req.scale:
        snap, _taluk_map = generate_scale_snapshot(n_facilities=req.scale)
        _PLAN_SNAPSHOTS[plan_id] = (snap, _taluk_map)
    else:
        snap = _load_snapshot(req.mode)

    print(f"[QPI AI OPT] Facilities: {len(snap.facilities)}, Drugs: {len(snap.drugs)}, Lots: {len(snap.lots)}")
    log.info("snapshot_loaded", facilities=len(snap.facilities), drugs=len(snap.drugs), lots=len(snap.lots))

    _publish_progress(plan_id, "positions", "Computing FEFO positions")
    positions = compute_all_positions(snap)

    _publish_progress(plan_id, "candidates", "Generating candidates")
    candidates = generate_candidates(snap, positions)

    print(f"[QPI AI OPT] Candidates: {len(candidates)}")
    log.info("candidates_generated", count=len(candidates))

    solver_meta: dict[str, Any] = {}

    if req.solver == "qubo":
        orders, solver_meta = _run_qubo_pipeline(
            snap, candidates, plan_id, req.overrides,
        )
        if not orders:
            log.info("qubo_fallback_to_greedy")
            _publish_progress(plan_id, "solving", "QUBO empty, falling back to greedy F4")
            orders = greedy_f4(snap)
            solver_meta["solver_tier"] = solver_meta.get("solver_tier", "greedy-f4-fallback")
    elif req.solver == "greedy":
        _publish_progress(plan_id, "solving", "Running greedy phone-call")
        orders = greedy_phone_call(snap)
        solver_meta = {"solver_tier": "greedy-phone-call"}
    else:
        _publish_progress(plan_id, "solving", "Running greedy F4 solver")
        orders = greedy_f4(snap)
        solver_meta = {"solver_tier": "greedy-f4"}

    _publish_progress(plan_id, "metrics", "Computing plan metrics")
    metrics = compute_metrics(orders, snap)

    plan = {
        "id": plan_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": req.mode,
        "solver_tier": solver_meta.get("solver_tier", req.solver),
        "energy": solver_meta.get("energy"),
        "gap_to_milp": None,
        "variables": len(candidates),
        "constraints": sum(1 for c in candidates if not c.feasibility.feasible),
        "transfers": len(orders),
        "shortage_reduction": metrics.shortage_reduction,
        "expiry_avoided": metrics.expiry_avoided_units,
        "cost_inr": metrics.total_cost_inr,
        "solver_meta": solver_meta,
    }

    order_dicts = [o.to_dict() for o in orders]
    candidate_dicts = [c.to_dict() for c in candidates]

    _publish_progress(plan_id, "persisting", "Saving plan to core-api")
    _persist_plan({
        "plan": plan,
        "orders": order_dicts,
        "candidates": candidate_dicts,
        "regret": [],
    })

    # Cache for benchmark
    if plan_id not in _PLAN_SNAPSHOTS:
        _PLAN_SNAPSHOTS[plan_id] = (snap, None)
    _PLAN_CANDIDATES[plan_id] = candidates
    _PLAN_ORDERS[plan_id] = orders
    _PLAN_METRICS[plan_id] = metrics

    # Register as live plan for auto re-plan
    global _LATEST_PLAN_ID
    _LATEST_PLAN_ID = plan_id
    set_live_plan(plan, orders, snap)

    _publish_progress(plan_id, "done", f"{len(orders)} transfers")

    print(f"[QPI AI OPT] Plan complete: {len(orders)} transfers, shortage reduction {metrics.shortage_reduction:.2%}")
    print("=" * 60)
    log.info("plan_complete", plan_id=plan_id, transfers=len(orders), shortage_reduction=round(metrics.shortage_reduction, 4))

    return {
        "plan": plan,
        "orders": order_dicts,
        "metrics": metrics.to_dict(),
    }


@router.get("/plan/{plan_id}")
async def get_plan(plan_id: str):
    if settings.USE_FIXTURES:
        from medbal_common.fixtures import CONTRACTS_DIR
        return json.loads((CONTRACTS_DIR / "plan-demo.json").read_text())
    try:
        resp = httpx.get(f"{CORE_API_URL}/orders", params={"plan_id": plan_id}, timeout=10.0)
        resp.raise_for_status()
        return {"plan_id": plan_id, "orders": resp.json()}
    except Exception as e:
        return {"plan_id": plan_id, "orders": [], "error": str(e)}


@router.get("/plan/{plan_id}/benchmark")
async def benchmark_plan(plan_id: str):
    """Compare solvers: no-transfer, greedy, greedy_f4, QUBO, MILP + zoning."""
    snap_entry = _PLAN_SNAPSHOTS.get(plan_id)
    if not snap_entry:
        snap = _load_snapshot("live")
        taluk_map = None
    else:
        snap, taluk_map = snap_entry

    candidates = _PLAN_CANDIDATES.get(plan_id)
    if candidates is None:
        positions = compute_all_positions(snap)
        candidates = generate_candidates(snap, positions)

    ven_priority = {code: drug.ven_priority for code, drug in snap.drugs.items()}
    shortages = {
        (fac_id, dc): pos.shortage
        for (fac_id, dc), pos in snap.positions.items()
        if pos.shortage > 0
    }

    rows: list[dict[str, Any]] = []

    # 1. No-transfer baseline
    no_transfer_metrics = compute_metrics([], snap)
    rows.append({
        "solver": "no-transfer",
        "objective": 0,
        "shortage_reduction": 0.0,
        "expiry_avoided_inr": 0,
        "waste_moved": 0,
        "trips": 0,
        "time_ms": 0,
    })

    # 2. Greedy phone-call
    t0 = time.perf_counter()
    pc_orders = greedy_phone_call(snap)
    pc_ms = (time.perf_counter() - t0) * 1000
    pc_m = compute_metrics(pc_orders, snap)
    rows.append({
        "solver": "greedy-phone-call",
        "objective": round(sum(o.usable * (snap.drugs.get(o.drug_code) or snap.drugs.get("PCM")).unit_cost_inr for o in pc_orders), 2),
        "shortage_reduction": round(pc_m.shortage_reduction, 4),
        "expiry_avoided_inr": round(pc_m.expiry_avoided_inr, 2),
        "waste_moved": sum(o.usable for o in pc_orders),
        "trips": pc_m.trips,
        "time_ms": round(pc_ms, 2),
    })

    # 3. Greedy F4
    t0 = time.perf_counter()
    f4_orders = greedy_f4(snap)
    f4_ms = (time.perf_counter() - t0) * 1000
    f4_m = compute_metrics(f4_orders, snap)
    rows.append({
        "solver": "greedy-f4",
        "objective": round(sum(o.usable * (snap.drugs.get(o.drug_code) or snap.drugs.get("PCM")).unit_cost_inr for o in f4_orders), 2),
        "shortage_reduction": round(f4_m.shortage_reduction, 4),
        "expiry_avoided_inr": round(f4_m.expiry_avoided_inr, 2),
        "waste_moved": sum(o.usable for o in f4_orders),
        "trips": f4_m.trips,
        "time_ms": round(f4_ms, 2),
    })

    # 4. QUBO (solver chain)
    t0 = time.perf_counter()
    qubo_orders, q_meta = _run_qubo_pipeline(snap, candidates, plan_id, None)
    qubo_ms = (time.perf_counter() - t0) * 1000
    qubo_m = compute_metrics(qubo_orders, snap) if qubo_orders else no_transfer_metrics
    rows.append({
        "solver": f"qubo ({q_meta.get('solver_tier', 'unknown')})",
        "objective": round(q_meta.get("energy", 0) or 0, 4),
        "shortage_reduction": round(qubo_m.shortage_reduction, 4),
        "expiry_avoided_inr": round(qubo_m.expiry_avoided_inr, 2),
        "waste_moved": sum(o.usable for o in qubo_orders),
        "trips": qubo_m.trips,
        "time_ms": round(qubo_ms, 2),
    })

    # 5. MILP exact
    cfg = QUBOConfig()
    qubo_result = build_qubo(candidates, ven_priority, shortages, cfg)
    t0 = time.perf_counter()
    milp_result = solve_milp(
        candidates, ven_priority, shortages, qubo_result.norm_factor,
        time_limit_s=20.0,
    )
    milp_ms = (time.perf_counter() - t0) * 1000

    milp_orders: list[TransferOrder] = []
    for ci in milp_result.selected_indices:
        c = candidates[ci]
        drug = snap.drugs.get(c.drug_code)
        milp_orders.append(TransferOrder(
            id=f"ORD-M-{len(milp_orders)+1:03d}",
            src_facility_id=c.chunk.lot.facility_id,
            dst_facility_id=c.destination_id,
            drug_code=c.drug_code,
            drug_name=drug.name if drug else c.drug_code,
            batch_no=c.chunk.lot.batch_no,
            qty=c.chunk.qty,
            usable=c.usable,
            score=milp_result.objective,
            temperature_req="cold_chain" if (drug and drug.cold_chain) else "ambient",
        ))
    milp_m = compute_metrics(milp_orders, snap) if milp_orders else no_transfer_metrics

    rows.append({
        "solver": f"milp ({milp_result.status})",
        "objective": round(milp_result.objective, 4),
        "shortage_reduction": round(milp_m.shortage_reduction, 4),
        "expiry_avoided_inr": round(milp_m.expiry_avoided_inr, 2),
        "waste_moved": sum(o.usable for o in milp_orders),
        "trips": milp_m.trips,
        "time_ms": round(milp_ms, 2),
    })

    # Gap
    qubo_obj = q_meta.get("energy", 0) or 0
    milp_obj = milp_result.objective
    gap_pct = None
    if milp_obj != 0:
        gap_pct = round(abs(qubo_obj - milp_obj) / abs(milp_obj) * 100, 2)

    # Zoning comparison
    try:
        zr = zone_facilities(snap, mode="live" if not taluk_map else "scale", taluk_map=taluk_map)
        zoning_table = {
            "maxcut": {
                "partition": zr.zones,
                "cut_value": zr.cut_value,
                "intra_zone_cost": round(zr.intra_zone_cost, 2),
                "tier": zr.maxcut_result.tier,
                "approx_ratio": round(zr.maxcut_result.approx_ratio, 4) if zr.maxcut_result.approx_ratio == zr.maxcut_result.approx_ratio else None,
            },
            "kmeans": zr.kmeans_comparison,
        }
    except Exception as e:
        zoning_table = {"error": str(e)}

    return {
        "plan_id": plan_id,
        "benchmark": rows,
        "gap_qubo_to_milp_pct": gap_pct,
        "zoning": zoning_table,
    }


# ── Why-not endpoint ──────────────────────────────────────────────

@router.get("/whynot")
async def whynot_endpoint(facility: str, drug: str):
    """Explain residual shortage and every candidate that lost."""
    plan_id = _LATEST_PLAN_ID
    if not plan_id:
        return {"error": "No plan has been run yet"}

    snap_entry = _PLAN_SNAPSHOTS.get(plan_id)
    if not snap_entry:
        return {"error": f"Plan {plan_id} snapshot not found"}
    snap, _ = snap_entry

    candidates = _PLAN_CANDIDATES.get(plan_id, [])
    orders = _PLAN_ORDERS.get(plan_id, [])

    return compute_whynot(facility, drug, snap, candidates, orders)


# ── What-if endpoint ──────────────────────────────────────────────

class WhatIfRequest(BaseModel):
    overrides: list[dict[str, Any]]
    solver: str = "qubo"
    plan_id: str | None = None


@router.post("/whatif")
async def whatif_endpoint(req: WhatIfRequest):
    """Run pipeline on a copied snapshot with overrides. Never persists as live."""
    pid = req.plan_id or _LATEST_PLAN_ID
    if not pid:
        return {"error": "No plan has been run yet"}

    snap_entry = _PLAN_SNAPSHOTS.get(pid)
    if not snap_entry:
        return {"error": f"Plan {pid} snapshot not found"}
    snap, _ = snap_entry

    orders = _PLAN_ORDERS.get(pid, [])
    metrics = _PLAN_METRICS.get(pid)

    return run_whatif(
        req.overrides, snap, orders,
        live_metrics=metrics,
        solver=req.solver,
    )


# ── Eval / Replay endpoints ─────────────────────────────────────

_EVAL_JOBS: dict[str, dict[str, Any]] = {}


class EvalRequest(BaseModel):
    seeds: int = 20
    days: int = 28
    policies: str = "A,B,C,D,E"
    solver: str = "local"


@router.post("/eval/replay")
async def start_eval(req: EvalRequest):
    """Start a replay evaluation as a background job."""
    import threading
    job_id = f"eval-{uuid.uuid4().hex[:8]}"
    _EVAL_JOBS[job_id] = {"status": "running", "result": None}

    def _run():
        try:
            from app.eval.replay import run_single, aggregate, AggregatedResult
            policies = [p.strip() for p in req.policies.split(",")]
            seeds = list(range(1, req.seeds + 1))
            solver_override = req.solver if req.solver != "chain" else None
            all_agg = []
            for pol in policies:
                runs = [run_single(s, pol, req.days, solver_override=solver_override) for s in seeds]
                all_agg.append(aggregate(runs).to_dict())
            _EVAL_JOBS[job_id] = {"status": "done", "result": {"aggregated": all_agg}}
        except Exception as e:
            _EVAL_JOBS[job_id] = {"status": "error", "error": str(e)}

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {"job_id": job_id, "status": "running"}


@router.get("/eval/{job_id}")
async def get_eval(job_id: str):
    job = _EVAL_JOBS.get(job_id)
    if not job:
        return {"error": "Job not found"}
    return job


@router.get("/plan/{plan_id}/regret")
async def get_regret(plan_id: str, order_id: str | None = None):
    """Return regret ledger for a plan, optionally filtered to one order."""
    if settings.USE_FIXTURES:
        from medbal_common.fixtures import CONTRACTS_DIR
        demo = json.loads((CONTRACTS_DIR / "plan-demo.json").read_text())
        regret = demo.get("regret", [])
        if order_id:
            regret = [r for r in regret if r.get("order_id") == order_id]
        return regret

    solve = _PLAN_SOLVE.get(plan_id)
    if not solve:
        return []
    meta = solve.meta if hasattr(solve, "meta") else {}
    regret = meta.get("regret", [])
    if order_id:
        regret = [r for r in regret if r.get("order_id") == order_id]
    return regret
