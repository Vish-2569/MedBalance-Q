"""In-memory telemetry storage with 1-per-minute downsampling."""
from __future__ import annotations

import threading
from collections import defaultdict
from datetime import datetime

MAX_ENTRIES = 1440  # 24h at 1/min
MIN_INTERVAL_S = 60


class TelemetryStore:
    def __init__(self) -> None:
        self._data: dict[str, list[dict]] = defaultdict(list)
        self._last_ts: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def append(
        self,
        device_id: str,
        ts: str,
        temp_c: float | None,
        door_open: bool,
        battery: int,
        state: str,
    ) -> bool:
        """Store a reading if >= 60s since last stored reading for this device.
        Returns True if stored, False if skipped (downsampled)."""
        ts_dt = _parse_ts(ts)
        with self._lock:
            last = self._last_ts.get(device_id)
            if last is not None and (ts_dt - last).total_seconds() < MIN_INTERVAL_S:
                return False

            entry = {
                "timestamp": ts,
                "temperature_c": temp_c,
                "door_open": door_open,
                "battery": battery,
                "state": state,
            }
            buf = self._data[device_id]
            buf.append(entry)
            if len(buf) > MAX_ENTRIES:
                self._data[device_id] = buf[-MAX_ENTRIES:]
            self._last_ts[device_id] = ts_dt
            return True

    def get(self, device_id: str, since: str | None = None) -> list[dict]:
        with self._lock:
            buf = list(self._data.get(device_id, []))
        if since:
            since_dt = _parse_ts(since)
            buf = [e for e in buf if _parse_ts(e["timestamp"]) >= since_dt]
        return buf

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._last_ts.clear()


def _parse_ts(ts: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(ts)
