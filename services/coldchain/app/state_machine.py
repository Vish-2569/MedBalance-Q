"""Per-device cold-chain state machine.

States: OK → WARNING → EXCURSION → (6 good) → RECOVERED/OK
Thresholds: valid range 2–8 °C.
"""
from __future__ import annotations

from datetime import datetime, timedelta


TEMP_MIN = 2.0
TEMP_MAX = 8.0
CONSECUTIVE_BAD_FOR_EXCURSION = 3
CONSECUTIVE_GOOD_FOR_RECOVERY = 6
DOOR_OPEN_EXCURSION_SECONDS = 120


class DeviceState:
    OK = "OK"
    WARNING = "WARNING"
    EXCURSION = "EXCURSION"


def _is_good(temp_c: float | None) -> bool:
    if temp_c is None:
        return False
    return TEMP_MIN <= temp_c <= TEMP_MAX


class DeviceStateMachine:
    def __init__(
        self,
        device_id: str,
        vehicle_id: str | None = None,
        facility_id: str | None = None,
    ):
        self.device_id = device_id
        self.vehicle_id = vehicle_id
        self.facility_id = facility_id
        self.state: str = DeviceState.OK
        self.consecutive_bad: int = 0
        self.consecutive_good: int = 0
        self.last_temp: float | None = None
        self.last_seen: str | None = None
        self.excursion_since: str | None = None
        self._door_open_since: datetime | None = None

    def process_reading(
        self,
        ts: str,
        temp_c: float | None,
        door_open: bool = False,
        battery: int = 100,
    ) -> list[dict]:
        """Process one telemetry reading; return transition events (if any)."""
        self.last_temp = temp_c
        self.last_seen = ts
        events: list[dict] = []

        # --- door-open logic ---
        ts_dt = _parse_ts(ts)
        if door_open:
            if self._door_open_since is None:
                self._door_open_since = ts_dt
            elif (
                ts_dt - self._door_open_since
            ).total_seconds() > DOOR_OPEN_EXCURSION_SECONDS:
                if self.state != DeviceState.EXCURSION:
                    events.extend(self._enter_excursion(ts, temp_c))
                    return events
        else:
            self._door_open_since = None

        # --- temperature logic ---
        good = _is_good(temp_c)

        if self.state == DeviceState.OK:
            if good:
                self.consecutive_bad = 0
            else:
                self.consecutive_bad = 1
                self.state = DeviceState.WARNING
        elif self.state == DeviceState.WARNING:
            if good:
                self.consecutive_bad = 0
                self.consecutive_good = 0
                self.state = DeviceState.OK
            else:
                self.consecutive_bad += 1
                if self.consecutive_bad >= CONSECUTIVE_BAD_FOR_EXCURSION:
                    events.extend(self._enter_excursion(ts, temp_c))
        elif self.state == DeviceState.EXCURSION:
            if good:
                self.consecutive_good += 1
                if self.consecutive_good >= CONSECUTIVE_GOOD_FOR_RECOVERY:
                    events.extend(self._recover(ts, temp_c))
            else:
                self.consecutive_good = 0

        return events

    def _enter_excursion(self, ts: str, temp_c: float | None) -> list[dict]:
        self.state = DeviceState.EXCURSION
        self.consecutive_good = 0
        self.excursion_since = ts
        return [
            {
                "type": "excursion",
                "device_id": self.device_id,
                "vehicle_id": self.vehicle_id,
                "facility_id": self.facility_id,
                "temp_c": temp_c,
                "since": ts,
                "severity": "critical",
            }
        ]

    def _recover(self, ts: str, temp_c: float | None) -> list[dict]:
        self.state = DeviceState.OK
        self.consecutive_bad = 0
        self.consecutive_good = 0
        since = self.excursion_since
        self.excursion_since = None
        return [
            {
                "type": "recovered",
                "device_id": self.device_id,
                "vehicle_id": self.vehicle_id,
                "facility_id": self.facility_id,
                "temp_c": temp_c,
                "since": since,
                "severity": "resolved",
            }
        ]

    def to_status(self) -> dict:
        return {
            "device_id": self.device_id,
            "vehicle_id": self.vehicle_id,
            "facility_id": self.facility_id,
            "state": self.state,
            "temperature_c": self.last_temp,
            "last_seen": self.last_seen,
            "alert": self.state == DeviceState.EXCURSION,
        }


def _parse_ts(ts: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(ts)
