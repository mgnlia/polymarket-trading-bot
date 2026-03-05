"""Main trading agent — orchestrates all strategies."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Callable, Coroutine, Any

from backend.airdrop_score import AirdropTracker
from backend.config import settings
from backend.polymarket_client import fetch_markets
from backend.risk_manager import RiskManager
from backend.strategies.arbitrage import ArbitrageScanner
from backend.strategies.diversity_farmer import DiversityFarmer
from backend.strategies.market_maker import MarketMaker
from backend.strategies.momentum import MomentumTrader
from backend.strategies.scheduler import ActivityScheduler

logger = logging.getLogger(__name__)


class PolymarketAgent:
    """Orchestrates all Polymarket trading strategies."""

    def __init__(self):
        self.risk = RiskManager()
        self.arbitrage = ArbitrageScanner()
        self.market_maker = MarketMaker()
        self.momentum = MomentumTrader()
        self.diversity = DiversityFarmer()
        self.scheduler = ActivityScheduler()
        self.airdrop = AirdropTracker()

        self._running = False
        self._task: asyncio.Task | None = None
        self._event_log: deque[dict] = deque(maxlen=500)
        self._event_callbacks: list[Callable[[dict], Coroutine[Any, Any, None]]] = []
        self._markets_cache: list[dict] = []
        self._markets_updated: float = 0.0
        self._cycle_count: int = 0

    def add_event_callback(self, cb: Callable[[dict], Coroutine[Any, Any, None]]) -> None:
        self._event_callbacks.append(cb)

    def remove_event_callback(self, cb: Callable[[dict], Coroutine[Any, Any, None]]) -> None:
        self._event_callbacks.discard(cb) if hasattr(self._event_callbacks, 'discard') else None
        try:
            self._event_callbacks.remove(cb)
        except ValueError:
            pass

    async def _emit(self, event: dict) -> None:
        event.setdefault("ts", time.time())
        self._event_log.append(event)
        for cb in list(self._event_callbacks):
            try:
                await cb(event)
            except Exception as e:
                logger.debug(f"Event callback error: {e}")

    async def _get_markets(self) -> list[dict]:
        """Fetch markets with 5-minute cache."""
        if time.time() - self._markets_updated > 300:
            try:
                self._markets_cache = await fetch_markets(limit=100)
                self._markets_updated = time.time()
                logger.info(f"Fetched {len(self._markets_cache)} markets")
            except Exception as e:
                logger.warning(f"Failed to fetch markets: {e}")
                if not self._markets_cache:
                    # Fallback: generate synthetic markets for simulation
                    self._markets_cache = self._synthetic_markets()
        return self._markets_cache

    def _synthetic_markets(self) -> list[dict]:
        """Generate synthetic markets for pure simulation mode."""
        topics = [
            ("Will Bitcoin exceed $100k by end of 2025?", "crypto"),
            ("Will Trump win the 2024 presidential election?", "politics"),
            ("Will the Fed cut rates in Q1 2025?", "economics"),
            ("Will Ethereum ETF be approved by SEC?", "crypto"),
            ("Will Chiefs win Super Bowl LIX?", "sports"),
            ("Will US enter recession in 2025?", "economics"),
            ("Will OpenAI release GPT-5 in 2025?", "science"),
            ("Will Polymarket reach $10B volume in 2025?", "crypto"),
            ("Will Ukraine-Russia ceasefire happen in 2025?", "world-events"),
            ("Will Taylor Swift win Grammy AOTY 2025?", "entertainment"),
            ("Will Apple release AR glasses in 2025?", "science"),
            ("Will Solana flip Ethereum by market cap?", "crypto"),
            ("Will Lakers make playoffs 2024-25?", "sports"),
            ("Will US-China trade war escalate in 2025?", "world-events"),
            ("Will Kamala Harris run in 2028?", "politics"),
            ("Will inflation drop below 2% in 2025?", "economics"),
            ("Will SpaceX land on Mars by 2030?", "science"),
            ("Will Netflix lose subscribers in Q1 2025?", "entertainment"),
            ("Will Dogecoin reach $1 in 2025?", "crypto"),
            ("Will UK rejoin EU single market?", "world-events"),
        ]
        import random
        markets = []
        for i, (question, category) in enumerate(topics):
            mid = f"sim-market-{i:04d}"
            markets.append({
                "id": mid,
                "conditionId": mid,
                "question": question,
                "category": category,
                "active": True,
                "tokens": [
                    {"token_id": f"{mid}-yes", "outcome": "YES"},
                    {"token_id": f"{mid}-no", "outcome": "NO"},
                ],
            })
        return markets

    async def _run_cycle(self) -> None:
        """Execute one trading cycle across all strategies."""
        can_trade, reason = self.risk.can_trade()
        if not can_trade:
            await self._emit({"type": "risk_halt", "reason": reason})
            return

        markets = await self._get_markets()
        cycle_pnl = 0.0
        cycle_volume = 0.0

        # 1. Arbitrage
        if settings.ENABLE_ARBITRAGE:
            try:
                opps = await self.arbitrage.scan_markets(markets)
                for opp in opps[:3]:  # max 3 arbs per cycle
                    size = self.risk.kelly_size(0.85, 1.0 + opp.deviation, self.risk.portfolio_value)
                    if size > 0.5:
                        trade = await self.arbitrage.execute_opportunity(opp, size)
                        cycle_pnl += trade.get("profit_usd", 0)
                        cycle_volume += size * 2
                        await self._emit({"type": "arbitrage", **trade})
            except Exception as e:
                logger.warning(f"Arbitrage error: {e}")

        # 2. Market Making
        if settings.ENABLE_MARKET_MAKING:
            try:
                self.market_maker.update_positions()
                import random
                for market in random.sample(markets, min(3, len(markets))):
                    mid_price = random.uniform(0.3, 0.7)
                    size = self.risk.kelly_size(0.55, 1.03, self.risk.portfolio_value)
                    size = max(2.0, min(size, 10.0))
                    trade = await self.market_maker.quote_market(market, mid_price, size)
                    if trade and "pnl" in trade:
                        cycle_pnl += trade.get("pnl", 0)
                        cycle_volume += size
                        await self._emit({"type": "market_make", **trade})
            except Exception as e:
                logger.warning(f"Market making error: {e}")

        # 3. Momentum
        if settings.ENABLE_MOMENTUM:
            try:
                import random as _r
                sample = _r.sample(markets, min(10, len(markets)))
                trades = await self.momentum.scan_and_trade(sample, size_usd=5.0)
                for t in trades:
                    cycle_volume += t.get("size_usd", 0)
                    await self._emit({"type": "momentum", **t})
                closed = self.momentum.update_positions()
                for c in closed:
                    cycle_pnl += c.get("pnl", 0)
                    await self._emit({"type": "momentum_close", **c})
            except Exception as e:
                logger.warning(f"Momentum error: {e}")

        # 4. Diversity Farming
        if settings.ENABLE_DIVERSITY:
            try:
                trades = await self.diversity.farm_diversity(markets)
                self.diversity.simulate_pnl()
                for t in trades:
                    cycle_volume += t.get("size_usd", 0)
                    await self._emit({"type": "diversity", **t})
            except Exception as e:
                logger.warning(f"Diversity error: {e}")

        # Update risk manager
        self.risk.record_pnl(cycle_pnl)
        self._cycle_count += 1

        # Update airdrop score
        mm_stats = self.market_maker.get_stats()
        div_stats = self.diversity.get_stats()
        mom_stats = self.momentum.get_stats()
        arb_stats = self.arbitrage.get_stats()

        total_vol = (
            mm_stats["total_volume_usd"]
            + div_stats["total_volume_usd"]
            + arb_stats["total_trades"] * 10
        )
        total_pnl = (
            self.risk.portfolio_value - self.risk.peak_portfolio
            + arb_stats["total_profit_usd"]
            + mm_stats["total_pnl_usd"]
        )

        self.airdrop.update(
            total_volume=total_vol,
            total_pnl=total_pnl,
            win_rate=mom_stats["win_rate"],
            unique_markets=div_stats["unique_markets"],
            unique_categories=len(div_stats["category_breakdown"]),
            diversity_score=div_stats["diversity_score"],
            lp_volume=mm_stats["total_volume_usd"],
            lp_score=mm_stats["lp_score"],
        )

        await self._emit({
            "type": "cycle_complete",
            "cycle": self._cycle_count,
            "cycle_pnl": round(cycle_pnl, 4),
            "cycle_volume": round(cycle_volume, 2),
            "portfolio_value": self.risk.portfolio_value,
            "airdrop_score": self.airdrop.score.total_score,
            "airdrop_tier": self.airdrop.score.estimated_tier,
        })

    async def _loop(self) -> None:
        """Main agent loop."""
        while self._running:
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error(f"Agent cycle error: {e}")
                await self._emit({"type": "error", "message": str(e)})
            await asyncio.sleep(30)  # 30s between cycles

    async def start(self) -> dict:
        if self._running:
            return {"status": "already_running"}
        self._running = True
        self._task = asyncio.create_task(self._loop())
        await self._emit({"type": "agent_start", "simulation": settings.SIMULATION_MODE})
        return {"status": "started", "simulation": settings.SIMULATION_MODE}

    async def stop(self) -> dict:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        await self._emit({"type": "agent_stop"})
        return {"status": "stopped"}

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "simulation_mode": settings.SIMULATION_MODE,
            "cycle_count": self._cycle_count,
            "risk": self.risk.get_status(),
            "airdrop": self.airdrop.get_breakdown(),
            "strategies": {
                "arbitrage": self.arbitrage.get_stats(),
                "market_making": self.market_maker.get_stats(),
                "momentum": self.momentum.get_stats(),
                "diversity": self.diversity.get_stats(),
                "scheduler": self.scheduler.get_stats(),
            },
        }

    def get_event_log(self, n: int = 50) -> list[dict]:
        return list(self._event_log)[-n:]


agent = PolymarketAgent()
