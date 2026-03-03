"""
Arbitrage Strategy
Detects YES+NO mispricing: if YES + NO < 1 - threshold, both can be bought for profit.
Also detects single-side mispricing vs fair value.
"""
import logging
import random
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class ArbSignal:
    market_id: str
    question: str
    yes_price: float
    no_price: float
    edge: float  # Expected profit %
    strategy: str = "arbitrage"
    confidence: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ArbStats:
    signals_generated: int = 0
    trades_executed: int = 0
    total_profit: float = 0.0
    last_signal: Optional[str] = None


class ArbitrageStrategy:
    """
    Detects arbitrage opportunities in prediction markets.

    Core idea: In a binary market, YES + NO should sum to ~1.0 (minus fees).
    If YES + NO < 0.97, buying both sides guarantees profit.
    If YES or NO is mispriced vs a fair value estimate, trade the mispriced side.
    """

    def __init__(self):
        self.threshold = settings.arb_threshold
        self.stats = ArbStats()
        self.name = "arbitrage"
        logger.info(f"[Arbitrage] Initialized with threshold={self.threshold:.2%}")

    def scan(self, markets: list[dict]) -> list[ArbSignal]:
        """Scan markets for arbitrage opportunities."""
        signals = []

        for m in markets:
            yes = m.get("yes_price", 0.5)
            no = m.get("no_price", 0.5)
            total = yes + no

            # Classic two-sided arb: YES + NO < 1 - threshold
            if total < (1.0 - self.threshold):
                edge = (1.0 - total) * 100  # % profit
                confidence = min(0.99, (1.0 - total) / 0.15)
                signal = ArbSignal(
                    market_id=m["condition_id"],
                    question=m.get("question", ""),
                    yes_price=yes,
                    no_price=no,
                    edge=edge,
                    confidence=confidence,
                )
                signals.append(signal)
                logger.info(
                    f"[Arbitrage] 🎯 ARB signal: {m.get('question', '')[:50]} "
                    f"YES={yes:.3f} NO={no:.3f} edge={edge:.2f}%"
                )

            # One-sided: YES severely underpriced (< 0.1 or > 0.9 with low NO)
            elif yes < 0.15 and no < 0.80:
                edge = (0.15 - yes) * 100
                if edge > self.threshold * 100:
                    signals.append(ArbSignal(
                        market_id=m["condition_id"],
                        question=m.get("question", ""),
                        yes_price=yes,
                        no_price=no,
                        edge=edge,
                        confidence=0.6,
                    ))

        self.stats.signals_generated += len(signals)
        if signals:
            self.stats.last_signal = signals[-1].timestamp
        return signals

    def generate_orders(self, signal: ArbSignal, position_size: float = None) -> list[dict]:
        """Generate orders for an arbitrage signal."""
        size = min(position_size or settings.mm_order_size, settings.max_position_size)

        orders = []
        # Buy both YES and NO to lock in the spread
        for side, price in [("BUY", signal.yes_price), ("BUY", signal.no_price)]:
            orders.append({
                "market_id": signal.market_id,
                "question": signal.question,
                "side": side,
                "price": price,
                "size": size / 2,  # Split between YES and NO
                "order_type": "LIMIT",
                "strategy": "arbitrage",
                "expected_edge": signal.edge,
            })
        return orders

    def record_trade(self, pnl: float):
        self.stats.trades_executed += 1
        self.stats.total_profit += pnl

    def get_stats(self) -> dict:
        return {
            "signals_generated": self.stats.signals_generated,
            "trades_executed": self.stats.trades_executed,
            "total_profit": round(self.stats.total_profit, 4),
            "last_signal": self.stats.last_signal,
        }
