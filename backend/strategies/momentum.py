"""Momentum Trading — price movement & volume spike signals."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum


class Signal(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass
class MomentumSignal:
    market_id: str
    question: str
    signal: Signal
    price: float
    price_change_pct: float
    volume_spike: float
    confidence: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class MomentumPosition:
    market_id: str
    question: str
    direction: str  # YES or NO
    entry_price: float
    current_price: float
    size_usd: float
    pnl: float = 0.0
    opened_at: float = field(default_factory=time.time)


class MomentumTrader:
    """Trades on price momentum and volume spike signals."""

    def __init__(self):
        self.positions: list[MomentumPosition] = []
        self.trades: list[dict] = []
        self.signals: list[dict] = []
        self.total_pnl: float = 0.0
        self._entry_threshold: float = 0.05   # 5% price change
        self._volume_threshold: float = 2.0   # 2x average volume
        self._take_profit: float = 0.08
        self._stop_loss: float = 0.04
        self._max_positions: int = 5

    def _generate_signal(self, market: dict) -> MomentumSignal:
        """Generate a momentum signal (simulated)."""
        price = random.uniform(0.2, 0.8)
        price_change = random.gauss(0, 0.06)
        volume_spike = random.exponential(1.0) if hasattr(random, 'exponential') else random.uniform(0.5, 3.0)

        if price_change > self._entry_threshold and volume_spike > self._volume_threshold:
            signal = Signal.LONG
            confidence = min(0.95, 0.5 + abs(price_change) * 2)
        elif price_change < -self._entry_threshold and volume_spike > self._volume_threshold:
            signal = Signal.SHORT
            confidence = min(0.95, 0.5 + abs(price_change) * 2)
        else:
            signal = Signal.FLAT
            confidence = 0.3

        return MomentumSignal(
            market_id=market.get("id", ""),
            question=market.get("question", "")[:80],
            signal=signal,
            price=round(price, 4),
            price_change_pct=round(price_change * 100, 2),
            volume_spike=round(volume_spike, 2),
            confidence=round(confidence, 3),
        )

    async def scan_and_trade(self, markets: list[dict], size_usd: float) -> list[dict]:
        """Scan markets for momentum signals and execute trades."""
        new_trades = []
        for market in markets[:20]:
            if len(self.positions) >= self._max_positions:
                break

            sig = self._generate_signal(market)
            self.signals.append({
                "market_id": sig.market_id,
                "question": sig.question,
                "signal": sig.signal.value,
                "price": sig.price,
                "price_change_pct": sig.price_change_pct,
                "volume_spike": sig.volume_spike,
                "confidence": sig.confidence,
                "timestamp": sig.timestamp,
            })

            if sig.signal == Signal.FLAT or sig.confidence < 0.6:
                continue

            direction = "YES" if sig.signal == Signal.LONG else "NO"
            pos = MomentumPosition(
                market_id=sig.market_id,
                question=sig.question,
                direction=direction,
                entry_price=sig.price,
                current_price=sig.price,
                size_usd=size_usd,
            )
            self.positions.append(pos)

            trade = {
                "type": "momentum",
                "market_id": sig.market_id,
                "question": sig.question,
                "direction": direction,
                "entry_price": sig.price,
                "size_usd": size_usd,
                "signal": sig.signal.value,
                "confidence": sig.confidence,
                "simulated": True,
                "timestamp": time.time(),
            }
            self.trades.append(trade)
            new_trades.append(trade)

        return new_trades

    def update_positions(self) -> list[dict]:
        """Update positions with simulated price moves, apply TP/SL."""
        closed = []
        remaining = []
        for pos in self.positions:
            drift = random.gauss(0.005, 0.03)
            if pos.direction == "YES":
                pos.current_price = min(0.99, max(0.01, pos.current_price + drift))
            else:
                pos.current_price = min(0.99, max(0.01, pos.current_price - drift))

            price_move = (pos.current_price - pos.entry_price) / pos.entry_price
            if pos.direction == "NO":
                price_move = -price_move

            pos.pnl = price_move * pos.size_usd

            if price_move >= self._take_profit or price_move <= -self._stop_loss:
                self.total_pnl += pos.pnl
                closed.append({
                    "type": "momentum_close",
                    "market_id": pos.market_id,
                    "direction": pos.direction,
                    "entry_price": pos.entry_price,
                    "exit_price": pos.current_price,
                    "pnl": round(pos.pnl, 4),
                    "reason": "take_profit" if price_move >= self._take_profit else "stop_loss",
                    "timestamp": time.time(),
                })
            else:
                remaining.append(pos)

        self.positions = remaining
        return closed

    def get_positions(self) -> list[dict]:
        return [
            {
                "market_id": p.market_id,
                "question": p.question,
                "direction": p.direction,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "size_usd": p.size_usd,
                "pnl": round(p.pnl, 4),
                "pnl_pct": round((p.pnl / p.size_usd) * 100, 2) if p.size_usd else 0,
            }
            for p in self.positions
        ]

    def get_recent_trades(self, n: int = 20) -> list[dict]:
        return self.trades[-n:]

    def get_recent_signals(self, n: int = 10) -> list[dict]:
        return self.signals[-n:]

    def get_stats(self) -> dict:
        return {
            "active_positions": len(self.positions),
            "total_trades": len(self.trades),
            "total_pnl_usd": round(self.total_pnl, 4),
            "win_rate": self._calc_win_rate(),
        }

    def _calc_win_rate(self) -> float:
        closed = [t for t in self.trades if "pnl" in t]
        if not closed:
            return 0.0
        wins = sum(1 for t in closed if t.get("pnl", 0) > 0)
        return round(wins / len(closed) * 100, 1)
