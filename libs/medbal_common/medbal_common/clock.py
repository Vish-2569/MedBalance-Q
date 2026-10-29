from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone

import httpx

from medbal_common.settings import settings

_IST = timezone(timedelta(hours=5, minutes=30))
_cache: dict[str, float | dict | None] = {"value": None, "ts": 0.0}
_start_wall: float = time.monotonic()


def _fetch_clock() -> dict | None:
    now_mono = time.monotonic()
    if _cache["value"] is not None and (now_mono - _cache["ts"]) < 1.0:
        return _cache["value"]
    try:
        with httpx.Client(timeout=2.0) as c:
            resp = c.get(f"{settings.SIM_CONTROL_URL}/clock")
            resp.raise_for_status()
            data = resp.json()
            _cache["value"] = data
            _cache["ts"] = now_mono
            return data
    except Exception:
        return None


def _fallback_date() -> date:
    base = date.fromisoformat(settings.SIM_START_DATE)
    elapsed = time.monotonic() - _start_wall
    sim_days = int(elapsed / max(settings.SIM_DAY_SECONDS, 1))
    return base + timedelta(days=sim_days)


def _fallback_datetime() -> datetime:
    d = _fallback_date()
    return datetime(d.year, d.month, d.day, tzinfo=_IST)


def today() -> date:
    data = _fetch_clock()
    if data and "date" in data:
        return date.fromisoformat(data["date"])
    return _fallback_date()


def now() -> datetime:
    data = _fetch_clock()
    if data and "datetime" in data:
        return datetime.fromisoformat(data["datetime"])
    if data and "date" in data:
        d = date.fromisoformat(data["date"])
        return datetime(d.year, d.month, d.day, tzinfo=_IST)
    return _fallback_datetime()
