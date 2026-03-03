"""
Market Maker Strategy
Posts two-sided limit orders (bid + ask) around the mid price.
Earns the spread when both sides fill.
Optimized for airdrop: high volume, many markets, liquidity provision.
"""
import logging
import random
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class MMQuote:
    market_id: str
    question: str
    bid_price: float
    ask_price: float
    size: float
    mid_price: float
    expected_spread: float
    strategy: str = "market_maker"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class MMStats:
    quotes_posted: int = 0
    orders_placed: int = 0
    fills: int = 0
    spread_captured: float = 0.0
    markets_quoted: set = field(default_factory=set)


class MarketMakerStrategy:
    """
    Two-sided market making on Polymarket.
    Posts limit orders at bid and ask, capturing the spread.
    
    Airdrop benefit: creates volume + liquidity on many markets.
    """

    def __init__(self):
        self.min_spread = settings.mm_spread_min
        self.order_size = settings.mm_order_size
        self.stats = MMStats()
        self.name = "market_maker"
        self.active_quotes: dict[str, MMQuote] = {}
        logger.info(f"[MM] Initialized: min_spread={self.min_spread:.2%} size=${self.order_size}")

    def scan(self, markets: list[dict]) -> list[MMQuote]:
        """Find markets suitable for market making."""
        quotes = []

        for m in markets:
            yes = m.get("yes_price", 0.5)
            no = m.get("no_price", 0.5)
            spread = m.get("spread", abs(1.0 - yes - no))
            volume = m.get("volume", 0)

            # Need minimum spread to be profitable after fees
            if spread < self.min_spread:
                continue

            # Prefer markets with decent volume (active markets)
            if volume < 1000:
                continue

            mid = (yes + no) / 2
            half_spread = spread / 2 * 0.8  # Quote inside the spread

            quote = MMQuote(
                market_id=m["condition_id"],
                question=m.get("question", ""),
                bid_price=round(mid - half_spread, 4),
                ask_price=round(mid + half_spread, 4),
                size=self.order_size,
                mid_price=mid,
                expected_spread=spread,
            )
            quotes.append(quote)
            self.stats.markets_quoted.add(m["condition_id"])

        self.stats.quotes_posted += len(quotes)
        if quotes:
            logger.info(f"[MM] Generated {len(quotes)} quotes across {len(self.stats.markets_quoted)} markets")
        return quotes

    def generate_orders(self, quote: MMQuote) -> list[dict]:
        """Generate bid + ask limit orders for a quote."""
        return [
            {
                "market_id": quote.market_id,
                "question": quote.question,
                "side": "BUY",
                "price": quote.bid_price,
                "size": quote.size,
                "order_type": "LIMIT",
                "strategy": "market_maker",
                "expected_spread": quote.expected_spread,
            },
            {
                "market_id": quote.market_id,
                "question": quote.question,
                "side": "SELL",
                "price": quote.ask_price,
                "size": quote.size,
                "order_type": "LIMIT",
                "strategy": "market_maker",
                "expected_spread": quote.expected_spread,
            },
        ]

    def estimate_pnl(self, quote: MMQuote, fill_rate: float = 0.6) -> float:
        """Estimate P&L from a quote assuming fill_rate of both sides."""
        spread_captured = quote.expected_spread * quote.size
        return spread_captured * fill_rate

    def record_fill(self, spread: float):
        self.stats.fills += 1
        self.stats.spread_captured += spread
        self.stats.orders_placed += 2

    def get_stats(self) -> dict:
        return {
            "quotes_posted": self.stats.quotes_posted,
            "orders_placed": self.stats.orders_placed,
            "fills": self.stats.fills,
            "spread_captured": round(self.stats.spread_captured, 4),
            "markets_quoted": len(self.stats.markets_quoted),
        }
