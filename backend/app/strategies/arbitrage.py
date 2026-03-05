"""
Arbitrage strategy — YES + NO price deviation scanner.

Detects when YES_price + NO_price deviates from 1.0 by more than
the threshold (default 2%) plus estimated taker fee.

PnL can be NEGATIVE due to:
- Slippage: simulated via Gaussian noise on fill price
- Partial fills: not all arb legs may execute at expected price
- Fee drag: taker fee eats into thin arb margins
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from ..config import settings
from ..risk import RiskManager


TAKER_FEE = 0.005  # 0.5% per side


@dataclass
class ArbSignal:
    market_id: str
    market_question: str
    yes_price: float
    no_price: float
    deviation: float
    side: str  # "buy_yes" or "buy_no"
    size_usd: float
    expected_pnl: float
    actual_pnl: float
    executed: bool


def scan_arb_opportunities(markets: list[dict], risk: RiskManager) -> list[ArbSignal]:
    """Scan markets for YES+NO sum deviations and simulate execution."""
    signals: list[ArbSignal] = []
    threshold = settings.ARB_THRESHOLD_PCT + (2 * TAKER_FEE)

    for m in markets:
        prices = m.get("outcomePrices", [])
        if len(prices) < 2:
            continue
        yes_p = float(prices[0])
        no_p = float(prices[1])
        total = yes_p + no_p
        deviation = abs(total - 1.0)

        if deviation < threshold:
            continue

        # Determine side: if sum > 1, sell both (short); if sum < 1, buy both
        side = "buy_yes" if total < 1.0 else "buy_no"

        # Kelly sizing based on estimated win probability
        win_prob = min(0.85, 0.5 + deviation * 5)  # higher deviation = more confident
        size = risk.kelly_bet_size(win_prob, win_payout=deviation, loss_payout=1.0)
        if size < 0.50:
            continue

        market_id = m.get("id", "unknown")
        if not risk.can_open_position(market_id, size):
            continue

        # --- Realistic execution simulation ---
        # Slippage: Gaussian noise (can make arb unprofitable)
        slippage = random.gauss(0, 0.008)  # mean=0, std=0.8%
        # Fee cost both sides
        fee_cost = size * 2 * TAKER_FEE
        # Partial fill probability
        fill_rate = random.uniform(0.6, 1.0)
        effective_size = size * fill_rate

        # Raw arb profit = deviation * effective_size
        raw_profit = deviation * effective_size
        # Actual PnL includes slippage and fees — CAN BE NEGATIVE
        actual_pnl = raw_profit - fee_cost - (slippage * effective_size)

        executed = True
        risk.record_position(market_id, effective_size if side == "buy_yes" else -effective_size)
        risk.update_equity(actual_pnl)

        signals.append(
            ArbSignal(
                market_id=market_id,
                market_question=m.get("question", ""),
                yes_price=yes_p,
                no_price=no_p,
                deviation=deviation,
                side=side,
                size_usd=round(effective_size, 2),
                expected_pnl=round(raw_profit, 4),
                actual_pnl=round(actual_pnl, 4),
                executed=executed,
            )
        )

    return signals
