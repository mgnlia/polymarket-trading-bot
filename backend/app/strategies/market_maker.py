"""
Market Maker strategy — bid/ask spread provisioning.

Tracks net inventory per market and manages inventory risk.
Pairs bid and ask fills on both sides of the book.

PnL can be NEGATIVE due to:
- Adverse selection (informed traders pick off stale quotes)
- Inventory risk (net position moves against us)
- Slippage on rebalancing trades
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..config import settings
from ..risk import RiskManager


@dataclass
class MMInventory:
    """Track market maker inventory per market."""

    market_id: str
    net_position: float = 0.0  # positive = long, negative = short
    total_bought: float = 0.0
    total_sold: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    avg_buy_price: float = 0.0
    avg_sell_price: float = 0.0
    fills: list[dict] = field(default_factory=list)


@dataclass
class MMSignal:
    market_id: str
    market_question: str
    bid_price: float
    ask_price: float
    spread: float
    bid_filled: bool
    ask_filled: bool
    fill_size: float
    pnl: float
    inventory_after: float


class MarketMakerEngine:
    """Stateful market maker with inventory tracking."""

    def __init__(self) -> None:
        self.inventories: dict[str, MMInventory] = {}

    def _get_inventory(self, market_id: str) -> MMInventory:
        if market_id not in self.inventories:
            self.inventories[market_id] = MMInventory(market_id=market_id)
        return self.inventories[market_id]

    def _extract_yes_no_prices(self, market: dict) -> tuple[float, float] | None:
        yes_price = market.get("yes_price")
        no_price = market.get("no_price")
        if yes_price is not None and no_price is not None:
            return float(yes_price), float(no_price)

        prices = market.get("outcomePrices", [])
        if len(prices) < 2:
            return None

        return float(prices[0]), float(prices[1])

    def run(self, markets: list[dict], risk: RiskManager) -> list[MMSignal]:
        signals: list[MMSignal] = []
        spread_pct = settings.mm_spread_min

        for m in markets:
            parsed_prices = self._extract_yes_no_prices(m)
            if parsed_prices is None:
                continue

            yes_price, _ = parsed_prices
            mid_price = yes_price
            market_id = m.get("condition_id") or m.get("id", "unknown")
            inv = self._get_inventory(market_id)

            # Skew quotes based on inventory to reduce risk
            inventory_skew = -inv.net_position * 0.002  # push price away from heavy side
            bid_price = mid_price - (spread_pct / 2) + inventory_skew
            ask_price = mid_price + (spread_pct / 2) + inventory_skew

            bid_price = max(0.01, min(0.99, bid_price))
            ask_price = max(0.01, min(0.99, ask_price))

            # Simulate fill probability — wider spread = less fills
            bid_fill_prob = max(0.1, 0.5 - spread_pct * 5)
            ask_fill_prob = max(0.1, 0.5 - spread_pct * 5)

            bid_filled = random.random() < bid_fill_prob
            ask_filled = random.random() < ask_fill_prob

            if not bid_filled and not ask_filled:
                continue

            # Size via Kelly
            size = risk.kelly_size(win_prob=0.52, win_pct=spread_pct, loss_pct=0.05)
            if size < 0.25:
                size = 0.25  # minimum quote size

            can_trade, _ = risk.can_trade(size)
            if not can_trade:
                continue

            pnl = 0.0

            if bid_filled:
                # We bought — adverse selection risk
                adverse = random.gauss(0, 0.015)  # can move against us
                fill_price = bid_price + abs(random.gauss(0, 0.003))  # slippage on buy = pay more
                inv.net_position += size
                inv.total_bought += size
                inv.avg_buy_price = fill_price
                pnl -= adverse * size  # adverse selection cost
                inv.fills.append({"side": "buy", "price": fill_price, "size": size})

            if ask_filled:
                # We sold
                adverse = random.gauss(0, 0.015)
                fill_price = ask_price - abs(random.gauss(0, 0.003))  # slippage on sell = receive less
                inv.net_position -= size
                inv.total_sold += size
                inv.avg_sell_price = fill_price
                pnl -= adverse * size
                inv.fills.append({"side": "sell", "price": fill_price, "size": size})

            # Spread capture when both sides fill
            if bid_filled and ask_filled:
                spread_capture = (ask_price - bid_price) * size
                pnl += spread_capture

            # Inventory risk penalty — larger inventory = more risk
            inventory_cost = abs(inv.net_position) * 0.005 * random.uniform(0.5, 2.0)
            pnl -= inventory_cost

            inv.realized_pnl += pnl

            signals.append(
                MMSignal(
                    market_id=market_id,
                    market_question=m.get("question", ""),
                    bid_price=round(bid_price, 4),
                    ask_price=round(ask_price, 4),
                    spread=round(ask_price - bid_price, 4),
                    bid_filled=bid_filled,
                    ask_filled=ask_filled,
                    fill_size=round(size, 2),
                    pnl=round(pnl, 4),
                    inventory_after=round(inv.net_position, 2),
                )
            )

        return signals
