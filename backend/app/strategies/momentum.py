"""
Momentum strategy — price movement + volume spike signals.

Enters when price moves beyond entry threshold with volume confirmation.
Exits when price reversal exceeds exit threshold.

PnL can be NEGATIVE: momentum can reverse (whipsaw), slippage on
entry/exit, and false breakouts eat capital.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from ..config import settings
from ..risk import RiskManager


@dataclass
class MomentumSignal:
    market_id: str
    market_question: str
    direction: str  # "long" or "short"
    entry_price: float
    current_price: float
    price_change_pct: float
    volume_spike: bool
    size_usd: float
    pnl: float
    action: str  # "entry" or "exit" or "hold"


def run_momentum(markets: list[dict], risk: RiskManager) -> list[MomentumSignal]:
    """Scan for momentum signals and simulate entries/exits."""
    signals: list[MomentumSignal] = []

    for m in markets:
        prices = m.get("outcomePrices", [])
        if len(prices) < 2:
            continue

        current_price = float(prices[0])
        market_id = m.get("id", "unknown")
        volume = float(m.get("volume", 0))

        # Simulate recent price change (in real mode would compare to historical)
        price_change = random.gauss(0, 0.06)  # mean=0, std=6%
        volume_spike = volume > 200000 or random.random() < 0.3

        abs_change = abs(price_change)

        if abs_change < settings.MOMENTUM_ENTRY_THRESHOLD:
            continue

        if not volume_spike:
            continue

        direction = "long" if price_change > 0 else "short"

        # Kelly sizing: higher conviction for stronger moves
        win_prob = min(0.65, 0.45 + abs_change * 2)
        size = risk.kelly_bet_size(win_prob, win_payout=abs_change * 3, loss_payout=1.0)
        if size < 0.50:
            continue

        if not risk.can_open_position(market_id, size):
            continue

        # Simulate trade outcome — momentum can REVERSE (whipsaw)
        # True continuation probability decreases with move size (mean reversion)
        continuation_prob = max(0.3, 0.6 - abs_change)
        continues = random.random() < continuation_prob

        entry_slippage = abs(random.gauss(0, 0.005))
        entry_price = current_price + (entry_slippage if direction == "long" else -entry_slippage)

        if continues:
            # Momentum continues — profit with noise
            exit_move = abs(random.gauss(abs_change * 0.5, abs_change * 0.3))
            pnl = exit_move * size
        else:
            # Whipsaw / reversal — LOSS
            reversal = abs(random.gauss(abs_change * 0.4, abs_change * 0.5))
            pnl = -(reversal * size + entry_slippage * size)

        # Transaction costs
        pnl -= size * 0.005  # taker fee

        risk.record_position(market_id, size if direction == "long" else -size)
        risk.update_equity(pnl)

        signals.append(
            MomentumSignal(
                market_id=market_id,
                market_question=m.get("question", ""),
                direction=direction,
                entry_price=round(entry_price, 4),
                current_price=round(current_price, 4),
                price_change_pct=round(price_change * 100, 2),
                volume_spike=volume_spike,
                size_usd=round(size, 2),
                pnl=round(pnl, 4),
                action="entry",
            )
        )

    return signals
