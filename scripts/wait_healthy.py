"""Wait until all MedBalance-Q services report healthy, or timeout."""
from __future__ import annotations

import sys
import time
import urllib.request
import json

SERVICES = [
    ("gateway",     "http://localhost:8080/api/core/health"),
    ("core-api",    "http://localhost:8001/health"),
    ("ingest-ai",   "http://localhost:8002/health"),
    ("genai",       "http://localhost:8003/health"),
    ("forecast",    "http://localhost:8004/health"),
    ("optimizer",   "http://localhost:8005/health"),
    ("coldchain",   "http://localhost:8006/health"),
    ("sim-control", "http://localhost:8100/health"),
]

TIMEOUT = 180
POLL_INTERVAL = 3


def _check(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read())
            return data.get("status", "ok")
    except Exception:
        return None


def main() -> None:
    start = time.monotonic()
    ready: set[str] = set()

    while time.monotonic() - start < TIMEOUT:
        for name, url in SERVICES:
            if name in ready:
                continue
            status = _check(url)
            if status in ("ok", "degraded"):
                ready.add(name)
                elapsed = time.monotonic() - start
                print(f"  {name:15s} ready ({status}) at {elapsed:.0f}s")

        if len(ready) == len(SERVICES):
            total = time.monotonic() - start
            print(f"\nAll {len(SERVICES)} services healthy in {total:.0f}s")
            return

        time.sleep(POLL_INTERVAL)

    missing = [n for n, _ in SERVICES if n not in ready]
    print(f"\nTIMEOUT after {TIMEOUT}s — still waiting on: {', '.join(missing)}",
          file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
