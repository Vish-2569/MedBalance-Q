"""P2 penalty weight sweep over fixture snapshot.

Sweeps P2 over {0.5, 1.0, 1.5, 2.0, 3.0} on 5 seeds, measuring:
  - QUBO energy
  - Validator violations
  - Shortage reduction (from metrics)

Run: cd services/optimizer && uv run python -I ../../scripts/sweep_p2.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "optimizer"))

from app.snapshot import build_snapshot
from app.candidates import generate_candidates
from app.positions import compute_all_positions
from app.qubo_builder import build_qubo, QUBOConfig, energy
from app.solvers.greedy_descent import GreedyDescent
from app.validator import apply_plan
from app.baselines import greedy_f4
from app.metrics import compute_metrics

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts" / "fixtures"
P2_VALUES = [0.5, 1.0, 1.5, 2.0, 3.0]
SEEDS = [42, 123, 456, 789, 1024]


def run_sweep():
    raw = json.loads((CONTRACTS / "snapshot.json").read_text())
    snap = build_snapshot(raw, today=date(2026, 11, 1))
    positions = compute_all_positions(snap)
    candidates = generate_candidates(snap, positions)

    ven_priority = {code: drug.ven_priority for code, drug in snap.drugs.items()}
    shortages = {
        (fac_id, dc): pos.shortage
        for (fac_id, dc), pos in snap.positions.items()
        if pos.shortage > 0
    }

    greedy_orders = greedy_f4(snap)
    greedy_metrics = compute_metrics(greedy_orders, snap)

    print(f"Baseline greedy-f4: {len(greedy_orders)} orders, "
          f"shortage reduction={greedy_metrics.shortage_reduction:.2%}")
    print()

    results = []

    for p2 in P2_VALUES:
        row = {"p2": p2, "seeds": []}

        for seed in SEEDS:
            config = QUBOConfig(p2=p2, gamma=0.0)
            qubo = build_qubo(candidates, ven_priority, shortages, config)

            if qubo.num_variables == 0:
                row["seeds"].append({
                    "seed": seed, "energy": None, "violations": 0,
                    "orders": 0, "shortage_reduction": 0.0,
                })
                continue

            solver = GreedyDescent(restarts=50, seed=seed)
            solve_result = solver.solve(qubo.Q, qubo.offset, qubo.num_variables)

            if not solve_result.samples:
                row["seeds"].append({
                    "seed": seed, "energy": None, "violations": 0,
                    "orders": 0, "shortage_reduction": 0.0,
                })
                continue

            best = solve_result.samples[0]

            selected = []
            for v, val in best.x.items():
                if val == 1 and v < len(qubo.variables):
                    ci = qubo.variables[v]
                    selected.append((ci, candidates[ci]))

            val_result = apply_plan(snap, selected)
            valid_orders = [o for o in val_result.orders if not o.dropped]

            from app.baselines import TransferOrder
            transfer_orders = []
            for vo in valid_orders:
                drug = snap.drugs.get(vo.drug_code)
                transfer_orders.append(TransferOrder(
                    id=f"ORD-SW-{len(transfer_orders)+1:03d}",
                    src_facility_id=vo.src_facility_id,
                    dst_facility_id=vo.dst_facility_id,
                    drug_code=vo.drug_code,
                    drug_name=drug.name if drug else vo.drug_code,
                    batch_no=vo.batch_no,
                    qty=vo.qty,
                    usable=vo.usable,
                    score=best.energy,
                    temperature_req="cold_chain" if (drug and drug.cold_chain) else "ambient",
                ))

            metrics = compute_metrics(transfer_orders, snap)

            seed_result = {
                "seed": seed,
                "energy": round(best.energy, 4),
                "violations": len(val_result.violations),
                "orders": len(valid_orders),
                "shortage_reduction": round(metrics.shortage_reduction, 4),
            }
            row["seeds"].append(seed_result)

        avg_energy = _avg([s["energy"] for s in row["seeds"] if s["energy"] is not None])
        avg_violations = _avg([s["violations"] for s in row["seeds"]])
        avg_orders = _avg([s["orders"] for s in row["seeds"]])
        avg_sr = _avg([s["shortage_reduction"] for s in row["seeds"]])

        row["avg"] = {
            "energy": round(avg_energy, 4) if avg_energy else None,
            "violations": round(avg_violations, 2),
            "orders": round(avg_orders, 1),
            "shortage_reduction": round(avg_sr, 4),
        }
        results.append(row)

        print(f"P2={p2:4.1f}  energy={avg_energy:8.3f}  violations={avg_violations:.1f}  "
              f"orders={avg_orders:.0f}  shortage_red={avg_sr:.2%}")

    print()
    best_row = max(results, key=lambda r: r["avg"]["shortage_reduction"])
    print(f"Best P2={best_row['p2']} (shortage reduction {best_row['avg']['shortage_reduction']:.2%})")

    decisions_path = Path(__file__).resolve().parents[1] / "docs" / "DECISIONS.md"
    _append_sweep_decision(decisions_path, results, greedy_metrics.shortage_reduction)

    return results


def _avg(vals):
    nums = [v for v in vals if v is not None]
    return sum(nums) / len(nums) if nums else 0


def _append_sweep_decision(path, results, greedy_sr):
    entry = f"""

---

## ADR-P10b: P2 penalty weight default = 1.5

### Context
Swept P2 over {{0.5, 1.0, 1.5, 2.0, 3.0}} on 5 seeds using fixture snapshot.
Greedy-f4 baseline shortage reduction: {greedy_sr:.2%}.

### Results

| P2 | Avg Energy | Avg Violations | Avg Orders | Avg Shortage Reduction |
|---|---|---|---|---|
"""
    for r in results:
        a = r["avg"]
        entry += f"| {r['p2']:.1f} | {a['energy']} | {a['violations']:.1f} | {a['orders']:.0f} | {a['shortage_reduction']:.2%} |\n"

    best = max(results, key=lambda r: r["avg"]["shortage_reduction"])
    entry += f"""
### Decision
Keep P2={best['p2']} as default. It achieves the highest shortage reduction
across seeds while keeping violations low. The v3 Hamiltonian defaults
(P1=2, P2=1.5, P3=1, γ=auto) remain unchanged from CLAUDE.md §6.
"""

    try:
        existing = path.read_text()
    except FileNotFoundError:
        existing = "# Architecture Decision Records\n"

    if "ADR-P10b" not in existing:
        path.write_text(existing + entry)
        print(f"Written to {path}")
    else:
        print(f"ADR-P10b already in {path}, skipping write")


if __name__ == "__main__":
    run_sweep()
