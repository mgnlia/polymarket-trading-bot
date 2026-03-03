"""
Airdrop Optimization Engine
Tracks metrics that maximize Polymarket airdrop eligibility:
1. Market diversity (50+ unique markets)
2. Trading volume (USDC traded)
3. Profitability (positive win rate)
4. Liquidity provision (limit orders)
"""
import logging
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class AirdropMetrics:
    total_volume: float = 0.0
    markets_traded: set = field(default_factory=set)
    limit_orders: int = 0
    market_orders: int = 0
    profitable_trades: int = 0
    total_trades: int = 0
    total_pnl: float = 0.0
    last_updated: Optional[str] = None


class AirdropOptimizer:
    """
    Tracks and scores airdrop eligibility.
    
    Polymarket airdrop criteria (estimated):
    - Volume: more = better (target $10k+)
    - Diversity: 50+ different markets
    - Profitability: positive P&L preferred
    - Liquidity: limit orders > market orders
    """

    def __init__(self):
        self.metrics = AirdropMetrics()
        self.volume_target = settings.volume_target
        self.markets_target = settings.markets_target
        logger.info(
            f"[Airdrop] Targets: volume=${self.volume_target:,.0f} "
            f"markets={self.markets_target}"
        )

    def record_trade(self, market_id: str, volume: float, pnl: float, order_type: str = "LIMIT"):
        """Record a completed trade for airdrop tracking."""
        self.metrics.total_volume += volume
        self.metrics.markets_traded.add(market_id)
        self.metrics.total_trades += 1
        self.metrics.total_pnl += pnl

        if pnl > 0:
            self.metrics.profitable_trades += 1

        if order_type == "LIMIT":
            self.metrics.limit_orders += 1
        else:
            self.metrics.market_orders += 1

        self.metrics.last_updated = datetime.utcnow().isoformat()

    def score_diversity(self) -> float:
        """Score 0-100 based on market diversity."""
        count = len(self.metrics.markets_traded)
        return min(100.0, (count / self.markets_target) * 100)

    def score_volume(self) -> float:
        """Score 0-100 based on trading volume."""
        return min(100.0, (self.metrics.total_volume / self.volume_target) * 100)

    def score_profitability(self) -> float:
        """Score 0-100 based on win rate."""
        if self.metrics.total_trades == 0:
            return 0.0
        win_rate = self.metrics.profitable_trades / self.metrics.total_trades
        return min(100.0, win_rate * 100 * 1.5)  # 67% win rate = 100 score

    def score_liquidity(self) -> float:
        """Score 0-100 based on limit order ratio."""
        total = self.metrics.limit_orders + self.metrics.market_orders
        if total == 0:
            return 0.0
        limit_ratio = self.metrics.limit_orders / total
        return min(100.0, limit_ratio * 100 * 1.2)  # 83% limit = 100 score

    def overall_score(self) -> float:
        """Weighted overall airdrop score."""
        return (
            self.score_diversity() * 0.30 +
            self.score_volume() * 0.30 +
            self.score_profitability() * 0.20 +
            self.score_liquidity() * 0.20
        )

    def get_tier(self) -> str:
        score = self.overall_score()
        if score >= 80:
            return "Diamond"
        elif score >= 60:
            return "Gold"
        elif score >= 40:
            return "Silver"
        else:
            return "Bronze"

    def get_report(self) -> dict:
        """Full airdrop status report."""
        return {
            "scores": {
                "diversity": round(self.score_diversity(), 1),
                "volume": round(self.score_volume(), 1),
                "profitability": round(self.score_profitability(), 1),
                "liquidity": round(self.score_liquidity(), 1),
                "overall": round(self.overall_score(), 1),
            },
            "tier": self.get_tier(),
            "metrics": {
                "total_volume": round(self.metrics.total_volume, 2),
                "markets_traded": len(self.metrics.markets_traded),
                "total_trades": self.metrics.total_trades,
                "profitable_trades": self.metrics.profitable_trades,
                "limit_orders": self.metrics.limit_orders,
                "market_orders": self.metrics.market_orders,
                "total_pnl": round(self.metrics.total_pnl, 4),
                "win_rate": round(
                    self.metrics.profitable_trades / max(1, self.metrics.total_trades) * 100, 1
                ),
                "last_updated": self.metrics.last_updated,
            },
            "targets": {
                "markets_target": self.markets_target,
                "volume_target": self.volume_target,
            },
            "recommendations": self._get_recommendations(),
        }

    def _get_recommendations(self) -> list[str]:
        recs = []
        if self.score_diversity() < 50:
            remaining = self.markets_target - len(self.metrics.markets_traded)
            recs.append(f"Trade {remaining} more unique markets to hit diversity target")
        if self.score_volume() < 50:
            remaining = self.volume_target - self.metrics.total_volume
            recs.append(f"Need ${remaining:,.0f} more volume for full score")
        if self.score_liquidity() < 60:
            recs.append("Increase limit order ratio (reduce market orders)")
        if self.score_profitability() < 40:
            recs.append("Win rate below target — review momentum strategy thresholds")
        if not recs:
            recs.append("🎉 Excellent airdrop positioning! Keep trading.")
        return recs
