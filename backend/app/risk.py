"""Risk Management — position limits, daily loss limits, exposure tracking."""
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
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


class RiskManager:
    """
    Enforces risk limits:
    - Max open positions
    - Max position size
    - Daily loss limit
    - Total exposure cap
    """

    def __init__(self):
        self.max_positions = settings.max_positions
        self.max_position_size = settings.max_position_size
        self.daily_loss_limit = settings.daily_loss_limit
        self.state = RiskState()
        logger.info(
            f"[Risk] Limits: max_pos={self.max_positions} "
            f"max_size=${self.max_position_size} daily_loss=${self.daily_loss_limit}"
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
        return True, "ok"

    def record_order_open(self, size: float):
        self.state.open_positions += 1
        self.state.total_exposure += size

    def record_order_close(self, size: float, pnl: float, volume: float):
        self.state.open_positions = max(0, self.state.open_positions - 1)
        self.state.total_exposure = max(0, self.state.total_exposure - size)
        self.state.daily_pnl += pnl
        self.state.daily_volume += volume
        if self.state.daily_pnl < -self.daily_loss_limit:
            self.state.halted = True
            self.state.halt_reason = f"daily loss limit ${self.daily_loss_limit} hit"
            logger.warning(f"[Risk] HALT: daily P&L = ${self.state.daily_pnl:.2f}")

    def get_status(self) -> dict:
        self._check_daily_reset()
        return {
            "open_positions": self.state.open_positions,
            "total_exposure": round(self.state.total_exposure, 2),
            "daily_pnl": round(self.state.daily_pnl, 4),
            "daily_volume": round(self.state.daily_volume, 2),
            "max_positions": self.max_positions,
            "daily_loss_limit": self.daily_loss_limit,
            "halted": self.state.halted,
            "halt_reason": self.state.halt_reason,
        }
