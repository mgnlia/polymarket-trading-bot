"""Diversity Farmer — spread positions across many market categories."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from backend.config import settings

CATEGORIES = [
    "politics", "crypto", "sports", "world-events",
    "science", "entertainment", "economics", "weather",
]


@dataclass
class DiversityPosition:
    market_id: str
    question: str
    category: str
    direction: str
    price: float
    size_usd: float
    pnl: float = 0.0
    timestamp: float = field(default_factory=time.time)


class DiversityFarmer:
    """Spreads small positions across many markets to maximize diversity metric."""

    def __init__(self):
        self.positions: list[DiversityPosition] = []
        self.trades: list[dict] = []
        self.unique_markets: set[str] = set()
        self.category_counts: dict[str, int] = {c: 0 for c in CATEGORIES}
        self.total_volume: float = 0.0
        self._min_size_usd: float = 1.0
        self._max_size_usd: float = 5.0

    def _detect_category(self, question: str) -> str:
        """Heuristic category detection from question text."""
        q = question.lower()
        if any(w in q for w in ["bitcoin", "eth", "crypto", "token", "defi", "btc"]):
            return "crypto"
        if any(w in q for w in ["president", "election", "senate", "congress", "vote", "trump", "biden"]):
            return "politics"
        if any(w in q for w in ["nba", "nfl", "soccer", "championship", "super bowl", "world cup"]):
            return "sports"
        if any(w in q for w in ["war", "conflict", "treaty", "un ", "nato"]):
            return "world-events"
        if any(w in q for w in ["gdp", "inflation", "fed", "interest rate", "recession"]):
            return "economics"
        if any(w in q for w in ["oscar", "grammy", "movie", "celebrity", "award"]):
            return "entertainment"
        return random.choice(CATEGORIES)

    async def farm_diversity(self, markets: list[dict], size_usd: float | None = None) -> list[dict]:
        """Place small positions across diverse markets."""
        new_trades = []
        size = size_usd or random.uniform(self._min_size_usd, self._max_size_usd)

        # Prioritize categories with fewer positions
        sorted_cats = sorted(self.category_counts, key=lambda c: self.category_counts[c])

        for market in markets:
            mid = market.get("id", "")
            if mid in self.unique_markets:
                continue

            question = market.get("question", "")
            category = self._detect_category(question)

            # Prefer underrepresented categories
            if category not in sorted_cats[:4] and len(self.unique_markets) > 10:
                if random.random() > 0.3:
                    continue

            direction = random.choice(["YES", "NO"])
            price = random.uniform(0.2, 0.8) if settings.SIMULATION_MODE else 0.5

            pos = DiversityPosition(
                market_id=mid,
                question=question[:80],
                category=category,
                direction=direction,
                price=round(price, 4),
                size_usd=round(size, 2),
            )
            self.positions.append(pos)
            self.unique_markets.add(mid)
            self.category_counts[category] = self.category_counts.get(category, 0) + 1
            self.total_volume += size

            trade = {
                "type": "diversity",
                "market_id": mid,
                "question": pos.question,
                "category": category,
                "direction": direction,
                "price": pos.price,
                "size_usd": pos.size_usd,
                "unique_markets_total": len(self.unique_markets),
                "simulated": True,
                "timestamp": time.time(),
            }
            self.trades.append(trade)
            new_trades.append(trade)

            if len(new_trades) >= 5:  # max 5 per cycle
                break

        return new_trades

    def simulate_pnl(self) -> None:
        """Simulate P&L drift on open positions."""
        for pos in self.positions:
            pos.pnl += random.gauss(0, pos.size_usd * 0.02)

    def get_positions(self) -> list[dict]:
        return [
            {
                "market_id": p.market_id,
                "question": p.question,
                "category": p.category,
                "direction": p.direction,
                "price": p.price,
                "size_usd": p.size_usd,
                "pnl": round(p.pnl, 4),
            }
            for p in self.positions[-30:]
        ]

    def get_recent_trades(self, n: int = 20) -> list[dict]:
        return self.trades[-n:]

    def get_stats(self) -> dict:
        return {
            "unique_markets": len(self.unique_markets),
            "total_trades": len(self.trades),
            "total_volume_usd": round(self.total_volume, 2),
            "category_breakdown": dict(self.category_counts),
            "diversity_score": self._calc_diversity_score(),
        }

    def _calc_diversity_score(self) -> float:
        """Higher score for even distribution across categories."""
        if not self.unique_markets:
            return 0.0
        counts = list(self.category_counts.values())
        total = sum(counts)
        if total == 0:
            return 0.0
        # Entropy-based score
        import math
        entropy = 0.0
        for c in counts:
            if c > 0:
                p = c / total
                entropy -= p * math.log2(p)
        max_entropy = math.log2(len(CATEGORIES))
        base = (entropy / max_entropy) * 100 if max_entropy > 0 else 0
        return round(base + len(self.unique_markets) * 0.5, 2)
