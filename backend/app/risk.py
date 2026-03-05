"""
Risk Management — position limits, daily loss limits, max drawdown circuit breaker, Kelly criterion.
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class RiskState:
    open_positions: int = 0
    total_exposure: float = 0.0
    daily_pnl: float = 0.0
    daily_volume: float = 0.0
    last_reset: date = field(default_factory=date.today)
    halted: bool = False
    halt_reason: Optional[str] = None
    # Drawdown tracking — peak-to-trough
    peak_equity: float = 0.0
    current_equity: float = 0.0
    max_drawdown_seen: float = 0.0


class RiskManager:
    """
    Enforces risk limits:
    - Max open positions
    - Max position size
    - Daily loss limit
    - Max drawdown circuit breaker (peak-to-trough from peak equity)
    - Kelly criterion position sizing (fractional Kelly)
    """

    def __init__(self):
        self.max_positions = settings.max_positions
        self.max_position_size = settings.max_position_size
        self.daily_loss_limit = settings.daily_loss_limit
        self.max_drawdown_pct = settings.max_drawdown_pct
        self.kelly_fraction = settings.kelly_fraction
        self.state = RiskState()
        logger.info(
            f"[Risk] Limits: max_pos={self.max_positions} "
            f"max_size=${self.max_position_size} daily_loss=${self.daily_loss_limit} "
            f"max_drawdown={self.max_drawdown_pct:.0%} kelly={self.kelly_fraction}"
        )

    def _check_daily_reset(self):
        today = date.today()
        if self.state.last_reset < today:
            logger.info("[Risk] Daily reset")
            self.state.daily_pnl = 0.0
            self.state.daily_volume = 0.0
            self.state.last_reset = today
            if self.state.halted and "daily" in (self.state.halt_reason or ""):
                self.state.halted = False
                self.state.halt_reason = None

    def _check_drawdown(self) -> tuple[bool, str]:
        """Check if peak-to-trough drawdown exceeds configured limit."""
        equity = self.state.current_equity
        peak = self.state.peak_equity
        if peak <= 0:
            return False, ""
        drawdown = (peak - equity) / peak
        self.state.max_drawdown_seen = max(self.state.max_drawdown_seen, drawdown)
        if drawdown >= self.max_drawdown_pct:
            return True, f"Max drawdown {drawdown:.1%} >= limit {self.max_drawdown_pct:.0%}"
        return False, ""

    def kelly_size(self, win_prob: float, win_pct: float, loss_pct: float) -> float:
        """
        Kelly criterion position size.
        f* = (p * b - q) / b  where b = win_pct/loss_pct, p = win_prob, q = 1-p
        Returns fractional Kelly (kelly_fraction * f*) capped at max_position_size.
        """
        if loss_pct <= 0 or win_pct <= 0:
            return self.max_position_size * 0.1
        b = win_pct / loss_pct
        p = win_prob
        q = 1.0 - p
        kelly_full = (p * b - q) / b
        kelly_full = max(0.0, kelly_full)  # Never bet negative
        size = kelly_full * self.kelly_fraction * self.max_position_size
        return round(min(size, self.max_position_size), 2)

    def can_trade(self, order_size: float) -> tuple[bool, str]:
        self._check_daily_reset()
        if self.state.halted:
            return False, f"Trading halted: {self.state.halt_reason}"
        if self.state.open_positions >= self.max_positions:
            return False, f"Max positions reached ({self.max_positions})"
        if order_size > self.max_position_size:
            return False, f"Order size ${order_size} exceeds max ${self.max_position_size}"
        if self.state.daily_pnl < -self.daily_loss_limit:
            self.state.halted = True
            self.state.halt_reason = f"daily loss limit ${self.daily_loss_limit} hit"
            return False, f"Daily loss limit hit: ${self.state.daily_pnl:.2f}"
        dd_breach, dd_reason = self._check_drawdown()
        if dd_breach:
            self.state.halted = True
            self.state.halt_reason = dd_reason
            logger.warning(f"[Risk] HALT (drawdown): {dd_reason}")
            return False, dd_reason
        return True, "ok"

    def record_order_open(self, size: float):
        self.state.open_positions += 1
        self.state.total_exposure += size

    def record_order_close(self, size: float, pnl: float, volume: float):
        self.state.open_positions = max(0, self.state.open_positions - 1)
        self.state.total_exposure = max(0, self.state.total_exposure - size)
        self.state.daily_pnl += pnl
        self.state.daily_volume += volume
        # Update equity curve for drawdown tracking
        self.state.current_equity += pnl
        if self.state.current_equity > self.state.peak_equity:
            self.state.peak_equity = self.state.current_equity
        # Check daily loss limit
        if self.state.daily_pnl < -self.daily_loss_limit:
            self.state.halted = True
            self.state.halt_reason = f"daily loss limit ${self.daily_loss_limit} hit"
            logger.warning(f"[Risk] HALT: daily P&L = ${self.state.daily_pnl:.2f}")
        # Check drawdown circuit breaker
        dd_breach, dd_reason = self._check_drawdown()
        if dd_breach and not self.state.halted:
            self.state.halted = True
            self.state.halt_reason = dd_reason
            logger.warning(f"[Risk] HALT (drawdown): {dd_reason}")

    def get_status(self) -> dict:
        self._check_daily_reset()
        peak = self.state.peak_equity
        equity = self.state.current_equity
        current_drawdown = (peak - equity) / peak if peak > 0 else 0.0
        return {
            "open_positions": self.state.open_positions,
            "total_exposure": round(self.state.total_exposure, 2),
            "daily_pnl": round(self.state.daily_pnl, 4),
            "daily_volume": round(self.state.daily_volume, 2),
            "max_positions": self.max_positions,
            "daily_loss_limit": self.daily_loss_limit,
            "max_drawdown_pct": self.max_drawdown_pct,
            "current_drawdown": round(current_drawdown, 4),
            "max_drawdown_seen": round(self.state.max_drawdown_seen, 4),
            "peak_equity": round(self.state.peak_equity, 4),
            "current_equity": round(self.state.current_equity, 4),
            "halted": self.state.halted,
            "halt_reason": self.state.halt_reason,
        }
