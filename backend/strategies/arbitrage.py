"""Arbitrage Scanner — detect YES+NO price deviations from $1.00."""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field

from backend.config import settings
from backend.polymarket_client import fetch_market_price, fetch_markets

logger = logging.getLogger(__name__)


@dataclass
class ArbitrageOpportunity:
    market_id: str
    question: str
    yes_price: float
    no_price: float
    deviation: float  # how far from 1.00
    expected_profit_pct: float
    timestamp: float = field(default_factory=time.time)


class ArbitrageScanner:
    """Scans YES+NO price pairs for arbitrage opportunities."""

    def __init__(self):
        self.opportunities: list[dict] = []
        self.trades: list[dict] = []
        self.total_profit: float = 0.0
        self.scan_count: int = 0
        self._min_deviation: float = 0.02  # 2% min deviation to trade

    async def scan_markets(self, markets: list[dict]) -> list[ArbitrageOpportunity]:
        """Scan a list of markets for arb opportunities."""
        opps = []
        tasks = []
        for market in markets[:30]:  # limit to 30 markets per scan
            tokens = market.get("tokens", [])
            if len(tokens) < 2:
                continue
            tasks.append(self._check_market(market, tokens))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, ArbitrageOpportunity):
                opps.append(r)

        self.scan_count += 1
        return opps

    async def _check_market(self, market: dict, tokens: list[dict]) -> ArbitrageOpportunity | None:
        try:
            yes_token = next((t for t in tokens if t.get("outcome", "").upper() == "YES"), tokens[0])
            no_token = next((t for t in tokens if t.get("outcome", "").upper() == "NO"), tokens[-1])

            if settings.SIMULATION_MODE:
                # Simulate realistic prices
                yes_price = round(random.uniform(0.3, 0.7), 3)
                no_price = round(random.uniform(0.3, 0.7), 3)
            else:
                yes_data = await fetch_market_price(yes_token["token_id"])
                no_data = await fetch_market_price(no_token["token_id"])
                yes_price = float(yes_data.get("mid", 0.5))
                no_price = float(no_data.get("mid", 0.5))

            total = yes_price + no_price
            deviation = abs(1.0 - total)

            if deviation >= self._min_deviation:
                profit_pct = deviation / total * 100
                return ArbitrageOpportunity(
                    market_id=market.get("id", ""),
                    question=market.get("question", "")[:80],
                    yes_price=yes_price,
                    no_price=no_price,
                    deviation=round(deviation, 4),
                    expected_profit_pct=round(profit_pct, 2),
                )
        except Exception as e:
            logger.debug(f"Arb check failed: {e}")
        return None

    async def execute_opportunity(self, opp: ArbitrageOpportunity, size_usd: float) -> dict:
        """Execute an arbitrage trade (simulation or live)."""
        if settings.SIMULATION_MODE:
            # Simulate execution with slippage
            slippage = random.uniform(0.001, 0.005)
            actual_profit = (opp.deviation - slippage) * size_usd
            trade = {
                "type": "arbitrage",
                "market_id": opp.market_id,
                "question": opp.question,
                "yes_price": opp.yes_price,
                "no_price": opp.no_price,
                "deviation": opp.deviation,
                "size_usd": size_usd,
                "profit_usd": round(actual_profit, 4),
                "simulated": True,
                "timestamp": time.time(),
            }
            self.trades.append(trade)
            self.total_profit += actual_profit
            return trade
        else:
            raise NotImplementedError("Live arbitrage execution requires EIP-712 signing")

    def get_recent_trades(self, n: int = 20) -> list[dict]:
        return self.trades[-n:]

    def get_stats(self) -> dict:
        return {
            "scan_count": self.scan_count,
            "total_trades": len(self.trades),
            "total_profit_usd": round(self.total_profit, 4),
            "recent_opportunities": len(self.opportunities),
        }
