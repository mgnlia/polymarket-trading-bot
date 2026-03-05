"""
Diversity Farmer Strategy
Spreads small positions across many markets (politics, crypto, sports, world events)
to maximize the market-diversity airdrop metric.
"""
import logging
import random
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Category weights for diversity scoring
CATEGORY_WEIGHTS = {
    "politics": 0.25,
    "crypto": 0.20,
    "sports": 0.20,
    "world_events": 0.15,
    "economics": 0.10,
    "science": 0.10,
}

MIN_POSITION_SIZE = 1.0   # $1 USDC minimum
MAX_POSITION_SIZE = 5.0   # $5 USDC maximum per market for diversity farming
TARGET_MARKETS = 50       # Aim to cover 50+ markets for top-tier airdrop score


@dataclass
class DiversitySignal:
    market_id: str
    question: str
    category: str
    yes_price: float
    no_price: float
    side: str           # BUY YES or BUY NO (whichever is cheaper/closer to 0.5)
    price: float
    size: float
    diversity_score_gain: float  # Estimated airdrop score gain from this trade


class DiversityFarmer:
    """
    Spreads positions across as many unique markets as possible.
    Prioritizes underrepresented categories for maximum diversity score.
    """

    def __init__(self):
        self._traded_markets: set[str] = set()
        self._category_counts: dict[str, int] = {cat: 0 for cat in CATEGORY_WEIGHTS}
        self._total_trades = 0
        self._total_volume = 0.0
        self._pnl = 0.0

    def _infer_category(self, question: str) -> str:
        """Infer market category from question text."""
        q = question.lower()
        if any(w in q for w in ["election", "president", "senate", "congress", "vote", "poll", "party"]):
            return "politics"
        if any(w in q for w in ["bitcoin", "eth", "crypto", "btc", "sol", "token", "defi", "nft"]):
            return "crypto"
        if any(w in q for w in ["nba", "nfl", "mlb", "nhl", "soccer", "football", "basketball", "championship"]):
            return "sports"
        if any(w in q for w in ["war", "conflict", "treaty", "un ", "nato", "climate", "disaster"]):
            return "world_events"
        if any(w in q for w in ["gdp", "inflation", "fed", "rate", "recession", "economy"]):
            return "economics"
        if any(w in q for w in ["ai", "research", "discovery", "space", "fda", "drug", "vaccine"]):
            return "science"
        return "world_events"  # Default

    def _category_priority(self, category: str) -> float:
        """Higher priority for underrepresented categories."""
        count = self._category_counts.get(category, 0)
        weight = CATEGORY_WEIGHTS.get(category, 0.1)
        # Priority decreases as count increases; weight boosts important categories
        return weight / (1 + count * 0.1)

    def scan(self, markets: list[dict]) -> list[DiversitySignal]:
        """Identify markets worth entering for diversity score."""
        signals = []

        for market in markets:
            market_id = market.get("id") or market.get("market_id", "")
            question = market.get("question", "")
            yes_price = float(market.get("yes_price", 0.5))
            no_price = float(market.get("no_price", 0.5))

            # Skip already-traded markets
            if market_id in self._traded_markets:
                continue

            # Skip markets with extreme prices (near-resolved)
            if yes_price > 0.95 or yes_price < 0.05:
                continue

            category = self._infer_category(question)
            priority = self._category_priority(category)

            # Buy whichever side is cheaper (closer to 0.5 from below)
            if abs(yes_price - 0.5) <= abs(no_price - 0.5):
                side, price = "BUY", yes_price
            else:
                side, price = "SELL", no_price

            # Scale size by priority (more for underrepresented categories)
            size = round(min(MAX_POSITION_SIZE, MIN_POSITION_SIZE + priority * 10), 2)
            score_gain = priority * 5.0  # Estimated airdrop score contribution

            signals.append(
                DiversitySignal(
                    market_id=market_id,
                    question=question,
                    category=category,
                    yes_price=yes_price,
                    no_price=no_price,
                    side=side,
                    price=price,
                    size=size,
                    diversity_score_gain=round(score_gain, 3),
                )
            )

        # Sort by diversity score gain (highest first)
        signals.sort(key=lambda s: s.diversity_score_gain, reverse=True)
        return signals[:10]  # Max 10 new markets per cycle

    def generate_order(self, signal: DiversitySignal) -> dict:
        return {
            "market_id": signal.market_id,
            "question": signal.question,
            "side": signal.side,
            "price": signal.price,
            "size": signal.size,
            "order_type": "LIMIT",
            "strategy": "diversity",
            "confidence": 0.5,
            "category": signal.category,
        }

    def record_trade(self, market_id: str, category: str, pnl: float, volume: float):
        self._traded_markets.add(market_id)
        self._category_counts[category] = self._category_counts.get(category, 0) + 1
        self._total_trades += 1
        self._total_volume += volume
        self._pnl += pnl

    def get_stats(self) -> dict:
        return {
            "total_trades": self._total_trades,
            "unique_markets": len(self._traded_markets),
            "category_coverage": dict(self._category_counts),
            "total_volume": round(self._total_volume, 2),
            "pnl": round(self._pnl, 4),
            "diversity_score": min(100, len(self._traded_markets) * 2),
        }
