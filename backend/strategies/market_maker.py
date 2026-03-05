"""Market Making — provide liquidity on both sides, earn airdrop LP score."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from backend.config import settings


@dataclass
class LiquidityPosition:
    market_id: str
    question: str
    bid_price: float
    ask_price: float
    spread: float
    size_usd: float
    side: str  # "both", "bid", "ask"
    pnl: float = 0.0
    created_at: float = field(default_factory=time.time)
    fills: int = 0


class MarketMaker:
    """Provides liquidity on both sides of prediction markets."""

    def __init__(self):
        self.positions: list[LiquidityPosition] = []
        self.trades: list[dict] = []
        self.lp_score: float = 0.0
        self.total_volume: float = 0.0
        self._base_spread: float = 0.03  # 3% spread
        self._max_positions: int = 10

    async def quote_market(self, market: dict, mid_price: float, size_usd: float) -> dict | None:
        """Place bid/ask quotes around mid price."""
        if len(self.positions) >= self._max_positions:
            return None

        spread = self._base_spread * random.uniform(0.8, 1.2)
        half = spread / 2
        bid = max(0.01, mid_price - half)
        ask = min(0.99, mid_price + half)

        pos = LiquidityPosition(
            market_id=market.get("id", ""),
            question=market.get("question", "")[:80],
            bid_price=round(bid, 4),
            ask_price=round(ask, 4),
            spread=round(spread, 4),
            size_usd=size_usd,
            side="both",
        )

        if settings.SIMULATION_MODE:
            # Simulate random fills
            fill_prob = random.random()
            if fill_prob > 0.6:
                fill_side = random.choice(["bid", "ask"])
                fill_price = pos.bid_price if fill_side == "bid" else pos.ask_price
                fill_pnl = (spread / 2) * size_usd * random.uniform(0.5, 1.0)
                pos.pnl += fill_pnl
                pos.fills += 1
                self.total_volume += size_usd
                self.lp_score += size_usd * 0.1  # LP score accrual

                trade = {
                    "type": "market_make",
                    "market_id": pos.market_id,
                    "question": pos.question,
                    "side": fill_side,
                    "fill_price": fill_price,
                    "spread": spread,
                    "size_usd": size_usd,
                    "pnl": round(fill_pnl, 4),
                    "lp_score_earned": round(size_usd * 0.1, 2),
                    "simulated": True,
                    "timestamp": time.time(),
                }
                self.trades.append(trade)
                self.positions.append(pos)
                return trade

        self.positions.append(pos)
        return {"market_id": pos.market_id, "bid": bid, "ask": ask, "spread": spread}

    def update_positions(self) -> None:
        """Remove stale positions (older than 1 hour in sim)."""
        now = time.time()
        self.positions = [p for p in self.positions if now - p.created_at < 3600]

    def get_positions(self) -> list[dict]:
        return [
            {
                "market_id": p.market_id,
                "question": p.question,
                "bid": p.bid_price,
                "ask": p.ask_price,
                "spread": p.spread,
                "size_usd": p.size_usd,
                "pnl": round(p.pnl, 4),
                "fills": p.fills,
            }
            for p in self.positions[-20:]
        ]

    def get_recent_trades(self, n: int = 20) -> list[dict]:
        return self.trades[-n:]

    def get_stats(self) -> dict:
        total_pnl = sum(p.pnl for p in self.positions)
        return {
            "active_positions": len(self.positions),
            "total_trades": len(self.trades),
            "total_volume_usd": round(self.total_volume, 2),
            "lp_score": round(self.lp_score, 2),
            "total_pnl_usd": round(total_pnl, 4),
        }
