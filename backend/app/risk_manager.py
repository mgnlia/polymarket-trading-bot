"""Risk Manager — position sizing, loss limits, exposure caps."""
import logging
from datetime import datetime, date, timezone
from typing import List, Dict, Any, Optional
from .config import settings
from . import database as db

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(self):
        self.daily_pnl: float = 0.0
        self.daily_date: Optional[date] = None
        self.open_positions: Dict[str, dict] = {}
        self.total_exposure: float = 0.0

    def _reset_daily_if_needed(self):
        today = date.today()
        if self.daily_date != today:
            self.daily_pnl = 0.0
            self.daily_date = today

    def check_daily_loss_limit(self) -> tuple[bool, str]:
        """Returns (allowed, reason)."""
        self._reset_daily_if_needed()
        if self.daily_pnl <= -settings.daily_loss_limit_usdc:
            return False, f"Daily loss limit hit: ${self.daily_pnl:.2f} (limit: ${settings.daily_loss_limit_usdc})"
        return True, "OK"

    def check_position_limit(self) -> tuple[bool, str]:
        """Check if we can open more positions."""
        open_count = len([p for p in self.open_positions.values() if p.get("status") == "open"])
        if open_count >= settings.max_open_positions:
            return False, f"Max positions reached: {open_count}/{settings.max_open_positions}"
        return True, "OK"

    def check_market_exposure(self, market_id: str, new_size: float) -> tuple[bool, str]:
        """Check if we already have too much exposure to a single market."""
        existing = self.open_positions.get(market_id, {})
        existing_size = existing.get("size", 0.0)
        if existing_size + new_size > settings.max_position_usdc * 2:
            return False, f"Market exposure too high: ${existing_size + new_size:.2f}"
        return True, "OK"

    def size_position(self, price: float, confidence: float = 0.5) -> float:
        """Kelly-based position sizing."""
        if price <= 0 or price >= 1:
            return 0.0

        # Kelly fraction: f = (p*b - q) / b where b = (1-price)/price
        p = confidence  # probability of winning
        q = 1 - p
        b = (1.0 - price) / price  # odds

        kelly = (p * b - q) / b if b > 0 else 0
        half_kelly = max(0, kelly * 0.5)  # half-Kelly for safety

        # Cap at max position
        size = min(half_kelly * settings.max_position_usdc, settings.max_position_usdc)
        return round(size, 2)

    def approve_trade(self, trade: dict) -> tuple[bool, str]:
        """Full risk check for a proposed trade."""
        # Daily loss check
        ok, msg = self.check_daily_loss_limit()
        if not ok:
            return False, msg

        # Position count check
        ok, msg = self.check_position_limit()
        if not ok:
            return False, msg

        # Market exposure check
        ok, msg = self.check_market_exposure(
            trade.get("market_id", ""),
            trade.get("size", 0)
        )
        if not ok:
            return False, msg

        # Min size check
        if trade.get("size", 0) < 1.0:
            return False, f"Size too small: ${trade.get('size', 0):.2f}"

        # Price sanity
        price = trade.get("price", 0)
        if not (0.01 <= price <= 0.99):
            return False, f"Price out of range: {price}"

        return True, "Approved"

    def record_trade_result(self, pnl: float, market_id: str, status: str = "closed"):
        """Update internal state after trade completes."""
        self._reset_daily_if_needed()
        self.daily_pnl += pnl
        if market_id in self.open_positions and status == "closed":
            self.open_positions[market_id]["status"] = "closed"
            self.open_positions[market_id]["realized_pnl"] = pnl

    def open_position(self, market_id: str, question: str, outcome: str,
                      price: float, size: float):
        """Register a new open position."""
        self.open_positions[market_id] = {
            "market_id": market_id,
            "question": question,
            "outcome": outcome,
            "entry_price": price,
            "size": size,
            "status": "open",
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_stats(self) -> dict:
        self._reset_daily_if_needed()
        open_count = len([p for p in self.open_positions.values() if p.get("status") == "open"])
        total_exposure = sum(
            p.get("size", 0) for p in self.open_positions.values()
            if p.get("status") == "open"
        )
        return {
            "daily_pnl": self.daily_pnl,
            "daily_loss_limit": settings.daily_loss_limit_usdc,
            "open_positions": open_count,
            "max_positions": settings.max_open_positions,
            "total_exposure": total_exposure,
            "max_exposure": settings.max_position_usdc * settings.max_open_positions,
        }


# Singleton
risk_manager = RiskManager()
