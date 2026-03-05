"""Risk management: Kelly sizing, drawdown circuit breaker, daily loss cap."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from backend.config import settings


@dataclass
class RiskManager:
    max_drawdown_pct: float = field(default_factory=lambda: settings.MAX_DRAWDOWN_PCT)
    daily_loss_cap: float = field(default_factory=lambda: settings.DAILY_LOSS_CAP_USD)
    max_position_usd: float = field(default_factory=lambda: settings.MAX_POSITION_USD)
    kelly_fraction: float = field(default_factory=lambda: settings.KELLY_FRACTION)

    # Runtime state
    peak_portfolio: float = 1000.0
    portfolio_value: float = 1000.0
    daily_pnl: float = 0.0
    _last_reset: datetime.date = field(default_factory=datetime.date.today)
    halted: bool = False
    halt_reason: str = ""

    def _check_reset(self) -> None:
        today = datetime.date.today()
        if today != self._last_reset:
            self.daily_pnl = 0.0
            self._last_reset = today
            if self.halted and "daily" in self.halt_reason:
                self.halted = False
                self.halt_reason = ""

    def record_pnl(self, pnl: float) -> None:
        self._check_reset()
        self.daily_pnl += pnl
        self.portfolio_value += pnl
        if self.portfolio_value > self.peak_portfolio:
            self.peak_portfolio = self.portfolio_value
        self._check_halt()

    def _check_halt(self) -> None:
        drawdown = (self.peak_portfolio - self.portfolio_value) / self.peak_portfolio
        if drawdown >= self.max_drawdown_pct:
            self.halted = True
            self.halt_reason = f"drawdown {drawdown:.1%} >= {self.max_drawdown_pct:.1%}"
            return
        if self.daily_pnl <= -self.daily_loss_cap:
            self.halted = True
            self.halt_reason = f"daily loss ${abs(self.daily_pnl):.2f} >= cap ${self.daily_loss_cap:.2f}"

    def kelly_size(self, win_prob: float, win_payout: float, bankroll: float | None = None) -> float:
        """Kelly criterion position size in USD."""
        if win_payout <= 0 or win_prob <= 0 or win_prob >= 1:
            return 0.0
        b = win_payout - 1
        q = 1 - win_prob
        kelly = (b * win_prob - q) / b
        kelly = max(0.0, kelly) * self.kelly_fraction
        bankroll = bankroll or self.portfolio_value
        size = kelly * bankroll
        return min(size, self.max_position_usd)

    def can_trade(self) -> tuple[bool, str]:
        self._check_reset()
        if self.halted:
            return False, self.halt_reason
        return True, ""

    def get_status(self) -> dict:
        self._check_reset()
        drawdown = (self.peak_portfolio - self.portfolio_value) / self.peak_portfolio
        return {
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "portfolio_value": round(self.portfolio_value, 2),
            "peak_portfolio": round(self.peak_portfolio, 2),
            "drawdown_pct": round(drawdown * 100, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_loss_cap": self.daily_loss_cap,
        }
