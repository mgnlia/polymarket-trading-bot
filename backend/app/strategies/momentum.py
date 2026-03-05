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
    entry_threshold = 0.05  # 5% price move triggers signal

    for m in markets:
        # Support both market formats
        current_price = float(m.get("yes_price") or (m.get("outcomePrices", [0.5]) + [0.5])[0])
        market_id = m.get("condition_id") or m.get("id", "unknown")
        question = m.get("question", "")
        volume = float(m.get("volume", 0))

        # Simulate recent price change (in real mode would compare to historical)
        price_change = random.gauss(0, 0.06)  # mean=0, std=6%
        volume_spike = volume > 200000 or random.random() < 0.3

        abs_change = abs(price_change)

        if abs_change < entry_threshold:
            continue

        if not volume_spike:
            continue

        direction = "long" if price_change > 0 else "short"

        # Kelly sizing: higher conviction for stronger moves
        win_prob = min(0.65, 0.45 + abs_change * 2)
        size = risk.kelly_size(win_prob=win_prob, win_pct=abs_change * 3, loss_pct=1.0)
        if size < 0.50:
            continue

        can_trade, _ = risk.can_trade(size)
        if not can_trade:
            continue

        # Simulate trade outcome — momentum can REVERSE (whipsaw)
        continuation_prob = max(0.3, 0.6 - abs_change)
        continues = random.random() < continuation_prob

        entry_slippage = abs(random.gauss(0, 0.005))
        entry_price = current_price + (entry_slippage if direction == "long" else -entry_slippage)

        if continues:
            exit_move = abs(random.gauss(abs_change * 0.5, abs_change * 0.3))
            pnl = exit_move * size
        else:
            reversal = abs(random.gauss(abs_change * 0.4, abs_change * 0.5))
            pnl = -(reversal * size + entry_slippage * size)

        # Transaction costs
        pnl -= size * 0.005  # taker fee

        risk.record_order_open(size)
        risk.record_order_close(size, pnl=pnl, volume=size * current_price)

        signals.append(
            MomentumSignal(
                market_id=market_id,
                market_question=question,
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
