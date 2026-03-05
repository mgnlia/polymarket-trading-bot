"""Anti-Sybil Activity Scheduler — Poisson-distributed timing, human-like behavior."""
from __future__ import annotations

import asyncio
import datetime
import logging
import math
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Coroutine, Any

logger = logging.getLogger(__name__)


@dataclass
class SchedulerStats:
    total_actions: int = 0
    sessions_completed: int = 0
    current_session_start: float = field(default_factory=time.time)
    daily_action_counts: dict[str, int] = field(default_factory=dict)
    hourly_rate: float = 0.0


class ActivityScheduler:
    """
    Schedules trading actions with human-like timing to avoid sybil detection.
    
    Key features:
    - Poisson-distributed inter-arrival times
    - Time-of-day weighting (less active at night)
    - Per-hour and per-day rate limits
    - Variable session lengths
    - Random pauses between actions
    """

    def __init__(
        self,
        max_actions_per_hour: int = 12,
        max_actions_per_day: int = 80,
        base_rate_per_hour: float = 6.0,
    ):
        self.max_actions_per_hour = max_actions_per_hour
        self.max_actions_per_day = max_actions_per_day
        self.base_rate = base_rate_per_hour  # Poisson lambda per hour
        self.stats = SchedulerStats()
        self._hourly_counts: dict[int, int] = {}  # hour -> count
        self._daily_count: int = 0
        self._last_reset_day: int = datetime.date.today().toordinal()
        self._callbacks: list[Callable[[], Coroutine[Any, Any, None]]] = []
        self._running: bool = False

    def _time_of_day_weight(self, hour: int) -> float:
        """Weight activity by time of day — less at night (2-7am), peak at 10am-2pm."""
        # Smooth curve: low overnight, peak midday
        night_dip = math.exp(-((hour - 4) ** 2) / 8)
        day_peak = math.exp(-((hour - 12) ** 2) / 18)
        evening = math.exp(-((hour - 20) ** 2) / 12)
        weight = 0.1 + day_peak * 0.7 + evening * 0.3 - night_dip * 0.5
        return max(0.05, weight)

    def _current_lambda(self) -> float:
        """Effective Poisson rate considering time-of-day."""
        hour = datetime.datetime.now().hour
        weight = self._time_of_day_weight(hour)
        return self.base_rate * weight

    def _check_reset(self) -> None:
        today = datetime.date.today().toordinal()
        if today != self._last_reset_day:
            self._daily_count = 0
            self._hourly_counts = {}
            self._last_reset_day = today

    def _current_hour_count(self) -> int:
        hour = datetime.datetime.now().hour
        return self._hourly_counts.get(hour, 0)

    def can_act(self) -> bool:
        self._check_reset()
        if self._daily_count >= self.max_actions_per_day:
            return False
        if self._current_hour_count() >= self.max_actions_per_hour:
            return False
        return True

    def record_action(self) -> None:
        self._check_reset()
        hour = datetime.datetime.now().hour
        self._hourly_counts[hour] = self._hourly_counts.get(hour, 0) + 1
        self._daily_count += 1
        self.stats.total_actions += 1

    def next_wait_seconds(self) -> float:
        """Sample next inter-arrival time from Poisson process."""
        lam = self._current_lambda()
        if lam <= 0:
            return 300.0
        # Exponential inter-arrival for Poisson process
        mean_wait = 3600.0 / lam
        wait = random.expovariate(1.0 / mean_wait)
        # Add human jitter: occasional longer pauses
        if random.random() < 0.1:
            wait *= random.uniform(2.0, 5.0)  # "bathroom break"
        return min(wait, 1800.0)  # cap at 30 min

    def session_length_seconds(self) -> float:
        """Random session length: 15-120 minutes."""
        return random.uniform(900, 7200)

    def add_callback(self, fn: Callable[[], Coroutine[Any, Any, None]]) -> None:
        self._callbacks.append(fn)

    async def run_session(self) -> None:
        """Run one trading session with human-like pacing."""
        session_end = time.time() + self.session_length_seconds()
        logger.info(f"Scheduler: starting session, {len(self._callbacks)} callbacks registered")

        while time.time() < session_end and self._running:
            if not self.can_act():
                logger.info("Scheduler: rate limit hit, waiting 5 min")
                await asyncio.sleep(300)
                continue

            for cb in self._callbacks:
                try:
                    await cb()
                except Exception as e:
                    logger.warning(f"Scheduler callback error: {e}")

            self.record_action()
            wait = self.next_wait_seconds()
            logger.debug(f"Scheduler: waiting {wait:.1f}s until next action")
            await asyncio.sleep(wait)

        self.stats.sessions_completed += 1

    async def run_forever(self) -> None:
        """Run sessions indefinitely with breaks between them."""
        self._running = True
        while self._running:
            await self.run_session()
            # Break between sessions: 5-30 min
            break_time = random.uniform(300, 1800)
            logger.info(f"Scheduler: session done, break for {break_time/60:.1f} min")
            await asyncio.sleep(break_time)

    def stop(self) -> None:
        self._running = False

    def get_stats(self) -> dict:
        self._check_reset()
        return {
            "total_actions": self.stats.total_actions,
            "sessions_completed": self.stats.sessions_completed,
            "daily_actions": self._daily_count,
            "daily_limit": self.max_actions_per_day,
            "current_hour_actions": self._current_hour_count(),
            "hourly_limit": self.max_actions_per_hour,
            "current_lambda": round(self._current_lambda(), 2),
            "can_act": self.can_act(),
        }
