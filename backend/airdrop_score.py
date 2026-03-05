"""Airdrop Score Tracker — estimates $POLY airdrop eligibility."""
from __future__ import annotations

import datetime
import time
from dataclasses import dataclass, field


@dataclass
class AirdropScore:
    """Tracks all metrics relevant to $POLY airdrop allocation."""

    # Volume metrics
    total_volume_usd: float = 0.0
    volume_score: float = 0.0

    # Profitability
    total_pnl_usd: float = 0.0
    win_rate_pct: float = 0.0
    profit_score: float = 0.0

    # Market diversity
    unique_markets: int = 0
    unique_categories: int = 0
    diversity_score: float = 0.0

    # Liquidity provision
    lp_volume_usd: float = 0.0
    lp_score: float = 0.0

    # Activity consistency
    active_days: int = 0
    current_streak_days: int = 0
    streak_score: float = 0.0

    # Account age
    account_age_days: int = 0
    age_score: float = 0.0

    # Composite
    total_score: float = 0.0
    estimated_tier: str = "none"

    last_updated: float = field(default_factory=time.time)


class AirdropTracker:
    """Aggregates strategy metrics into an airdrop score."""

    TIER_THRESHOLDS = [
        (2000, "diamond", "Top 1% — estimated max allocation"),
        (1000, "platinum", "Top 5% — large allocation"),
        (500, "gold", "Top 15% — significant allocation"),
        (200, "silver", "Top 30% — moderate allocation"),
        (50, "bronze", "Top 60% — small allocation"),
        (0, "none", "Below threshold — minimal/no allocation"),
    ]

    def __init__(self):
        self.score = AirdropScore()
        self._activity_dates: set[str] = set()
        self._start_date: datetime.date = datetime.date.today()

    def record_activity(self) -> None:
        today = datetime.date.today().isoformat()
        self._activity_dates.add(today)

    def update(
        self,
        total_volume: float,
        total_pnl: float,
        win_rate: float,
        unique_markets: int,
        unique_categories: int,
        diversity_score: float,
        lp_volume: float,
        lp_score: float,
    ) -> AirdropScore:
        self.record_activity()

        # Volume score: logarithmic, capped at 500
        import math
        self.score.total_volume_usd = total_volume
        self.score.volume_score = min(500.0, math.log1p(total_volume) * 30)

        # Profit score: win rate + absolute PnL
        self.score.total_pnl_usd = total_pnl
        self.score.win_rate_pct = win_rate
        profit_component = max(0, total_pnl) * 0.5
        winrate_component = max(0, win_rate - 50) * 3
        self.score.profit_score = min(300.0, profit_component + winrate_component)

        # Diversity score
        self.score.unique_markets = unique_markets
        self.score.unique_categories = unique_categories
        self.score.diversity_score = min(400.0, diversity_score + unique_markets * 1.5)

        # LP score
        self.score.lp_volume_usd = lp_volume
        self.score.lp_score = min(300.0, lp_score + math.log1p(lp_volume) * 20)

        # Streak score
        active_days = len(self._activity_dates)
        self.score.active_days = active_days
        streak = self._calc_streak()
        self.score.current_streak_days = streak
        self.score.streak_score = min(200.0, active_days * 3 + streak * 5)

        # Age score
        age = (datetime.date.today() - self._start_date).days
        self.score.account_age_days = age
        self.score.age_score = min(100.0, age * 2)

        # Total
        total = (
            self.score.volume_score
            + self.score.profit_score
            + self.score.diversity_score
            + self.score.lp_score
            + self.score.streak_score
            + self.score.age_score
        )
        self.score.total_score = round(total, 2)
        self.score.estimated_tier = self._get_tier(total)
        self.score.last_updated = time.time()

        return self.score

    def _calc_streak(self) -> int:
        """Calculate current consecutive day streak."""
        if not self._activity_dates:
            return 0
        streak = 0
        day = datetime.date.today()
        while day.isoformat() in self._activity_dates:
            streak += 1
            day -= datetime.timedelta(days=1)
        return streak

    def _get_tier(self, score: float) -> str:
        for threshold, tier, _ in self.TIER_THRESHOLDS:
            if score >= threshold:
                return tier
        return "none"

    def get_breakdown(self) -> dict:
        s = self.score
        tier_desc = next(
            (desc for thresh, tier, desc in self.TIER_THRESHOLDS if tier == s.estimated_tier),
            ""
        )
        return {
            "total_score": s.total_score,
            "estimated_tier": s.estimated_tier,
            "tier_description": tier_desc,
            "breakdown": {
                "volume": {
                    "score": round(s.volume_score, 2),
                    "max": 500,
                    "value_usd": round(s.total_volume_usd, 2),
                },
                "profitability": {
                    "score": round(s.profit_score, 2),
                    "max": 300,
                    "pnl_usd": round(s.total_pnl_usd, 2),
                    "win_rate_pct": round(s.win_rate_pct, 1),
                },
                "diversity": {
                    "score": round(s.diversity_score, 2),
                    "max": 400,
                    "unique_markets": s.unique_markets,
                    "unique_categories": s.unique_categories,
                },
                "liquidity": {
                    "score": round(s.lp_score, 2),
                    "max": 300,
                    "lp_volume_usd": round(s.lp_volume_usd, 2),
                },
                "consistency": {
                    "score": round(s.streak_score, 2),
                    "max": 200,
                    "active_days": s.active_days,
                    "current_streak": s.current_streak_days,
                },
                "account_age": {
                    "score": round(s.age_score, 2),
                    "max": 100,
                    "days": s.account_age_days,
                },
            },
        }
