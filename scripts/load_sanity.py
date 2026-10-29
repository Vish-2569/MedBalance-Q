"""Load sanity: run the optimizer plan N times and check for failures / memory growth.

Usage:
    python -I scripts/load_sanity.py [--base-url http://localhost:8080] [--iterations 20]
"""
from __future__ import annotations

import argparse
import sys
import time

import httpx

PLAN_PATH = "/api/optimizer/plan/run"
HEALTH_PATH = "/api/optimizer/health"
PLAN_BODY = {"solver": "qubo"}
TIMEOUT = 120.0


def _get_rss(base: str) -> int | None:
    try:
        resp = httpx.get(f"{base}{HEALTH_PATH}", timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("rss_mb") or data.get("rss") or None
    except Exception:
        pass
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="MedBalance-Q load sanity test")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--iterations", type=int, default=20)
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    n = args.iterations

    print("=" * 70)
    print(f"Load sanity: {n} plan runs against {base}")
    print("=" * 70)

    rows: list[dict] = []
    failures = 0

    for i in range(1, n + 1):
        rss_before = _get_rss(base)

        t0 = time.monotonic()
        error_msg = None
        status = 0
        n_orders = 0

        try:
            resp = httpx.post(
                f"{base}{PLAN_PATH}",
                json=PLAN_BODY,
                timeout=TIMEOUT,
            )
            status = resp.status_code
            if status == 200:
                body = resp.json()
                orders = body.get("orders", body.get("transfer_orders", []))
                n_orders = len(orders) if isinstance(orders, list) else 0
            else:
                error_msg = resp.text[:120]
                failures += 1
        except Exception as exc:
            error_msg = str(exc)[:120]
            failures += 1

        elapsed = time.monotonic() - t0
        rss_after = _get_rss(base)

        row = {
            "iter": i,
            "status": status,
            "time_s": round(elapsed, 2),
            "orders": n_orders,
            "rss_mb": rss_after,
            "error": error_msg,
        }
        rows.append(row)

        tag = "OK" if error_msg is None and status == 200 else "FAIL"
        rss_str = f"{rss_after}MB" if rss_after else "?"
        print(f"  [{i:2d}/{n}] {tag}  status={status}  orders={n_orders}  "
              f"time={elapsed:.1f}s  rss={rss_str}"
              + (f"  err={error_msg}" if error_msg else ""))

    # ── Summary ──────────────────────────────────────────────────
    print()
    print("-" * 70)
    print(f"{'#':>3}  {'Status':>6}  {'Time':>7}  {'Orders':>6}  {'RSS':>7}  Error")
    print("-" * 70)
    for r in rows:
        rss_str = f"{r['rss_mb']}MB" if r["rss_mb"] else "—"
        err_str = r["error"] or ""
        print(f"{r['iter']:3d}  {r['status']:6d}  {r['time_s']:6.1f}s  "
              f"{r['orders']:6d}  {rss_str:>7}  {err_str}")
    print("-" * 70)

    # Memory trend
    rss_vals = [r["rss_mb"] for r in rows if r["rss_mb"] is not None]
    memory_ok = True
    if len(rss_vals) >= 2:
        first, last = rss_vals[0], rss_vals[-1]
        growth = (last - first) / first if first > 0 else 0
        print(f"\nMemory: first={first}MB  last={last}MB  growth={growth:+.1%}")
        if growth > 0.50:
            print("FAIL: memory grew > 50%")
            memory_ok = False
        else:
            print("OK: memory growth within bounds")
    else:
        print("\nMemory: RSS not available from /health (skipping memory check)")

    # Verdict
    ok = failures == 0 and memory_ok
    print(f"\nFailures: {failures}/{n}")
    print(f"Result: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
