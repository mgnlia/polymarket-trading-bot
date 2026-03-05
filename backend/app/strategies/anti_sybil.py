"""
Anti-Sybil Activity Scheduler
Randomizes timing (Poisson distribution), human-like trade sizes,
variable session lengths to avoid bot-detection patterns.
"""
import logging
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionPlan:
    session_id: str
    start_time: datetime
    end_time: datetime
    planned_trades: int
    trade_intervals_seconds: list[float]  # Time between trades (Poisson)
    size_jitter_pct: float                # Random size variation ±%
    active: bool = True


class AntiSybilScheduler:
    """
    Wraps all strategy execution with human-like timing patterns.

    Key techniques:
    1. Poisson-distributed trade intervals (not uniform)
    2. Trade sizes drawn from lognormal distribution (not round numbers)
    3. Variable session lengths (15min to 4hr)
    4. Day-of-week and hour-of-day biases (active hours only)
    5. Occasional "rest days" (no trading) to mimic human behavior
    """

    def __init__(self):
        self._session: Optional[SessionPlan] = None
        self._trade_count_today = 0
        self._rest_day_probability = 0.10   # 10% chance of no trading on any given day
        self._last_trade_time: Optional[datetime] = None
        self._min_interval_seconds = 60     # At least 1 minute between trades
        self._sessions_completed = 0
        self._total_delays_applied = 0

    def _poisson_interval(self, mean_minutes: float) -> float:
        """Sample inter-trade interval from exponential distribution (Poisson process)."""
        # Exponential distribution: -mean * ln(uniform(0,1))
        u = random.random()
        interval_minutes = -mean_minutes * math.log(max(u, 1e-9))
        # Clamp: min 1 min, max 3x mean
        return max(60.0, min(interval_minutes * 60, mean_minutes * 3 * 60))

    def _human_trade_size(self, base_size: float, jitter_pct: float = 0.20) -> float:
        """
        Apply lognormal jitter to trade size to avoid round-number patterns.
        Also occasionally rounds to a 'human-like' value (5, 10, 25, 50).
        """
        sigma = jitter_pct
        multiplier = random.lognormvariate(0, sigma)
        size = base_size * multiplier

        # 30% chance of rounding to a human-like value
        if random.random() < 0.30:
            human_sizes = [1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 50]
            size = min(human_sizes, key=lambda x: abs(x - size))

        return round(max(1.0, size), 2)

    def _is_active_hour(self) -> bool:
        """Only trade during typical active hours (UTC 8am-11pm)."""
        hour = datetime.now(timezone.utc).hour
        return 8 <= hour <= 23

    def _is_rest_day(self) -> bool:
        """Occasionally skip an entire day."""
        # Use date as seed for consistency within a day
        day_seed = datetime.now(timezone.utc).toordinal()
        rng = random.Random(day_seed + 42)
        return rng.random() < self._rest_day_probability

    def should_trade_now(self) -> tuple[bool, str]:
        """Check if it's appropriate to place a trade right now."""
        if self._is_rest_day():
            return False, "Rest day — no trading scheduled"

        if not self._is_active_hour():
            return False, "Outside active trading hours (UTC 8am-11pm)"

        if self._last_trade_time is not None:
            elapsed = (datetime.now(timezone.utc) - self._last_trade_time).total_seconds()
            if elapsed < self._min_interval_seconds:
                wait = self._min_interval_seconds - elapsed
                return False, f"Min interval not met — wait {wait:.0f}s"

        return True, "ok"

    def get_next_trade_delay(self, mean_minutes: float = 15.0) -> float:
        """Return seconds to wait before next trade (Poisson-distributed)."""
        delay = self._poisson_interval(mean_minutes)
        self._total_delays_applied += 1
        return delay

    def humanize_order(self, order: dict) -> dict:
        """Apply human-like size jitter and timing metadata to an order."""
        order = dict(order)
        original_size = order.get("size", 5.0)
        order["size"] = self._human_trade_size(original_size)
        order["anti_sybil_applied"] = True
        order["scheduled_at"] = datetime.now(timezone.utc).isoformat()
        return order

    def record_trade(self):
        self._last_trade_time = datetime.now(timezone.utc)
        self._trade_count_today += 1

    def create_session(self, mean_trades: int = 8) -> SessionPlan:
        """Plan a trading session with randomized parameters."""
        import uuid
        now = datetime.now(timezone.utc)
        session_length_minutes = random.uniform(20, 240)  # 20min to 4hr
        end_time = now + timedelta(minutes=session_length_minutes)
        num_trades = max(1, int(random.gauss(mean_trades, mean_trades * 0.3)))
        mean_interval = session_length_minutes / max(num_trades, 1)
        intervals = [self._poisson_interval(mean_interval) for _ in range(num_trades)]
        self._session = SessionPlan(
            session_id=uuid.uuid4().hex[:8],
            start_time=now,
            end_time=end_time,
            planned_trades=num_trades,
            trade_intervals_seconds=intervals,
            size_jitter_pct=random.uniform(0.10, 0.30),
        )
        self._sessions_completed += 1
        logger.info(
            f"[AntiSybil] Session {self._session.session_id}: "
            f"{num_trades} trades over {session_length_minutes:.0f}min"
        )
        return self._session

    def get_stats(self) -> dict:
        return {
            "sessions_completed": self._sessions_completed,
            "trades_today": self._trade_count_today,
            "total_delays_applied": self._total_delays_applied,
            "last_trade_at": self._last_trade_time.isoformat() if self._last_trade_time else None,
            "active_session": self._session.session_id if self._session else None,
            "is_rest_day": self._is_rest_day(),
            "is_active_hour": self._is_active_hour(),
        }
