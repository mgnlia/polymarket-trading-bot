"""
Momentum / Sentiment Strategy
Uses price momentum and simulated news sentiment to take directional bets.
"""
import logging
import random
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class MomentumSignal:
    market_id: str
    question: str
    direction: str
    price: float
    confidence: float
    reason: str
    size: float
    strategy: str = "momentum"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class MomentumStats:
    signals_generated: int = 0
    trades_executed: int = 0
    correct_calls: int = 0
    total_profit: float = 0.0


class MomentumStrategy:
    """
    Momentum and sentiment-driven directional trading.
    Signal sources: price momentum, volume spikes, keyword sentiment.
    """

    def __init__(self):
        self.threshold = settings.momentum_threshold
        self.stats = MomentumStats()
        self.name = "momentum"
        self._price_history: dict[str, list[float]] = {}
        logger.info(f"[Momentum] Initialized with confidence threshold={self.threshold:.0%}")

    def update_price(self, market_id: str, price: float):
        if market_id not in self._price_history:
            self._price_history[market_id] = []
        hist = self._price_history[market_id]
        hist.append(price)
        if len(hist) > 20:
            hist.pop(0)

    def _calc_momentum(self, market_id: str) -> float:
        hist = self._price_history.get(market_id, [])
        if len(hist) < 3:
            return 0.0
        n = len(hist)
        x_mean = (n - 1) / 2
        y_mean = sum(hist) / n
        num = sum((i - x_mean) * (hist[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den > 0 else 0.0

    def _sim_sentiment(self, question: str) -> tuple[float, str]:
        bullish_keywords = ["win", "rise", "increase", "approve", "launch", "exceed", "gain"]
        bearish_keywords = ["fall", "decline", "reject", "fail", "lose", "cut", "ban"]
        q_lower = question.lower()
        bullish = sum(1 for kw in bullish_keywords if kw in q_lower)
        bearish = sum(1 for kw in bearish_keywords if kw in q_lower)
        noise = random.uniform(-0.2, 0.2)
        if bullish > bearish:
            score = min(0.9, 0.55 + (bullish - bearish) * 0.1 + noise)
            return score, f"Bullish keywords ({bullish} signals)"
        elif bearish > bullish:
            score = max(0.1, 0.45 - (bearish - bullish) * 0.1 + noise)
            return score, f"Bearish keywords ({bearish} signals)"
        else:
            return 0.5 + noise, "Neutral sentiment"

    def scan(self, markets: list[dict]) -> list[MomentumSignal]:
        signals = []
        for m in markets:
            yes = m.get("yes_price", 0.5)
            question = m.get("question", "")
            market_id = m["condition_id"]

            self.update_price(market_id, yes)
            sentiment_score, reason = self._sim_sentiment(question)

            if sentiment_score > 0.60 and yes < 0.70:
                direction = "YES"
                confidence = sentiment_score
                price = yes
                size = min(settings.mm_order_size * confidence, settings.max_position_size * 0.5)
            elif sentiment_score < 0.40 and yes > 0.30:
                direction = "NO"
                confidence = 1 - sentiment_score
                price = 1 - yes
                size = min(settings.mm_order_size * confidence, settings.max_position_size * 0.5)
            else:
                continue

            if confidence < self.threshold - 0.05:
                continue

            signal = MomentumSignal(
                market_id=market_id,
                question=question,
                direction=direction,
                price=price,
                confidence=confidence,
                reason=reason,
                size=round(size, 2),
            )
            signals.append(signal)
            logger.info(f"[Momentum] Signal: {question[:40]} → {direction} @ {price:.3f} conf={confidence:.2f}")

        self.stats.signals_generated += len(signals)
        return signals

    def generate_order(self, signal: MomentumSignal) -> dict:
        return {
            "market_id": signal.market_id,
            "question": signal.question,
            "side": "BUY",
            "price": signal.price,
            "size": signal.size,
            "order_type": "LIMIT",
            "strategy": "momentum",
            "direction": signal.direction,
            "confidence": signal.confidence,
            "reason": signal.reason,
        }

    def record_trade(self, correct: bool, pnl: float):
        self.stats.trades_executed += 1
        if correct:
            self.stats.correct_calls += 1
        self.stats.total_profit += pnl

    def get_win_rate(self) -> float:
        if self.stats.trades_executed == 0:
            return 0.0
        return self.stats.correct_calls / self.stats.trades_executed

    def get_stats(self) -> dict:
        return {
            "signals_generated": self.stats.signals_generated,
            "trades_executed": self.stats.trades_executed,
            "correct_calls": self.stats.correct_calls,
            "win_rate": round(self.get_win_rate(), 4),
            "total_profit": round(self.stats.total_profit, 4),
        }
