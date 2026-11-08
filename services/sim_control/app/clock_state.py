from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from medbal_common import bus
from medbal_common.settings import settings

_IST = timezone(timedelta(hours=5, minutes=30))


def _today_ist() -> date:
    return datetime.now(_IST).date()


class ClockState:
    def __init__(self):
        self.start_date = date.fromisoformat(settings.SIM_START_DATE)
        self._base_speed = float(settings.SIM_DAY_SECONDS)
        self._multiplier = 1.0
        self._secs_per_day = self._base_speed

        real_today = _today_ist()
        initial_days = max(0, (real_today - self.start_date).days)

        self.running = True
        self._start_wall: float = time.monotonic() - (initial_days * self._secs_per_day)
        self._paused_at_day = initial_days
        self._last_published_day = initial_days - 1

    @property
    def day_index(self) -> int:
        if not self.running:
            return self._paused_at_day
        if self._start_wall is None:
            return 0
        elapsed = time.monotonic() - self._start_wall
        return int(elapsed / max(self._secs_per_day, 0.01))

    @property
    def sim_date(self) -> date:
        return self.start_date + timedelta(days=self.day_index)

    @property
    def sim_time(self) -> datetime:
        d = self.sim_date
        return datetime(d.year, d.month, d.day, 10, 30, tzinfo=_IST)

    def start(self):
        if self.running:
            return
        self._start_wall = time.monotonic() - (self._paused_at_day * self._secs_per_day)
        self.running = True

    def pause(self):
        if not self.running:
            return
        self._paused_at_day = self.day_index
        self.running = False

    def set_speed(self, multiplier: float):
        current_day = self.day_index
        self._multiplier = max(multiplier, 0.1)
        self._secs_per_day = self._base_speed / self._multiplier
        if self.running:
            self._start_wall = time.monotonic() - (current_day * self._secs_per_day)
        else:
            self._paused_at_day = current_day

    def reset(self, seed: int | None = None):
        self.start_date = date.fromisoformat(settings.SIM_START_DATE)
        self._base_speed = float(settings.SIM_DAY_SECONDS)
        self._multiplier = 1.0
        self._secs_per_day = self._base_speed

        real_today = _today_ist()
        initial_days = max(0, (real_today - self.start_date).days)

        self.running = True
        self._start_wall = time.monotonic() - (initial_days * self._secs_per_day)
        self._paused_at_day = initial_days
        self._last_published_day = initial_days - 1

    def to_dict(self) -> dict:
        d = self.sim_date
        return {
            "sim_date": d.isoformat(),
            "date": d.isoformat(),
            "sim_time": self.sim_time.isoformat(),
            "datetime": self.sim_time.isoformat(),
            "speed": self._multiplier,
            "running": self.running,
            "day_index": self.day_index,
        }

    def check_and_publish_tick(self):
        if not self.running:
            return
        di = self.day_index
        if di > self._last_published_day:
            self._last_published_day = di
            try:
                bus.publish("clock.tick", {
                    "date": self.sim_date.isoformat(),
                    "day_index": di,
                })
            except Exception:
                pass


clock = ClockState()


@asynccontextmanager
async def tick_lifespan(app):
    _stop = asyncio.Event()

    async def _tick_loop():
        while not _stop.is_set():
            clock.check_and_publish_tick()
            try:
                await asyncio.wait_for(_stop.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(_tick_loop())
    yield
    _stop.set()
    await task
