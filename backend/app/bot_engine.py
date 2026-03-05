"""
Bot Engine — orchestrates all strategies, executor, risk, and airdrop tracking.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from .config import settings
from .strategies import scan_arb_opportunities, MarketMakerEngine, run_momentum
from .executor import OrderExecutor
from .risk import RiskManager
from .airdrop import AirdropOptimizer
from .market_scanner import refresh_markets

logger = logging.getLogger(__name__)


class LogBuffer:
    """Thread-safe circular log buffer for the dashboard."""

    def __init__(self, maxlen: int = 200):
        self._buf: list[dict] = []
        self._maxlen = maxlen

    def append(self, level: str, message: str, strategy: Optional[str] = None):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "strategy": strategy,
        }
        self._buf.append(entry)
        if len(self._buf) > self._maxlen:
            self._buf.pop(0)

    def tail(self, n: int = 50) -> list[dict]:
        return self._buf[-n:]


class BotEngine:
    """
    Central orchestrator for the Polymarket trading bot.
    Manages: strategy execution, order execution, risk, airdrop optimization.
    """

    def __init__(self):
        self.mm_engine = MarketMakerEngine()
        self.executor = OrderExecutor()
        self.risk = RiskManager()
        self.airdrop = AirdropOptimizer()
        self.logs = LogBuffer()

        self._running = False
        self._paused = False
        self._task: Optional[asyncio.Task] = None
        self._cycle_count = 0
        self._markets_scanned = 0
        self._trades: list[dict] = []

        # Per-strategy stats
        self._arb_trades = 0
        self._arb_pnl = 0.0
        self._mm_trades = 0
        self._mm_pnl = 0.0
        self._mom_trades = 0
        self._mom_pnl = 0.0

        mode = "SIMULATION" if settings.simulation_mode else "LIVE"
        self.logs.append("INFO", f"Bot engine initialized | Mode: {mode} | Strategies: ARB + MM + Momentum")
        logger.info("[Bot] Engine initialized")

    @property
    def running(self) -> bool:
        return self._running

    @property
    def paused(self) -> bool:
        return self._paused

    def start(self):
        if self._running:
            return
        self._running = True
        self._paused = False
        self._task = asyncio.create_task(self._run_loop())
        self.logs.append("SUCCESS", "Bot started — running all strategies")
        logger.info("[Bot] Started")

    def stop(self):
        self._running = False
        self._paused = False
        if self._task:
            self._task.cancel()
            self._task = None
        self.logs.append("INFO", "Bot stopped")
        logger.info("[Bot] Stopped")

    def pause(self):
        self._paused = not self._paused
        status = "paused" if self._paused else "resumed"
        self.logs.append("INFO", f"Bot {status}")
        logger.info(f"[Bot] {status.capitalize()}")

    async def run_cycle_once(self):
        await self._cycle()

    async def _run_loop(self):
        self.logs.append("INFO", f"Cycle interval: {settings.cycle_interval}s")
        while self._running:
            if not self._paused:
                try:
                    await self._cycle()
                except Exception as e:
                    logger.error(f"[Bot] Cycle error: {e}", exc_info=True)
                    self.logs.append("ERROR", f"Cycle error: {e}")
            await asyncio.sleep(settings.cycle_interval)

    async def _cycle(self):
        self._cycle_count += 1
        cycle_id = self._cycle_count
        self.logs.append("INFO", f"Cycle #{cycle_id} starting")

        markets = await refresh_markets()
        self._markets_scanned = len(markets)

        if not markets:
            self.logs.append("WARN", "No markets available — skipping cycle")
            return

        await self._run_arbitrage(markets)
        await self._run_market_maker(markets)
        await self._run_momentum(markets)

        self.logs.append(
            "INFO",
            f"Cycle #{cycle_id} complete | Trades: {len(self._trades)} | "
            f"Airdrop: {self.airdrop.overall_score():.0f}/100",
        )

    async def _run_arbitrage(self, markets: list[dict]):
        signals = scan_arb_opportunities(markets, self.risk)
        if not signals:
            return
        self.logs.append("SIGNAL", f"[ARB] {len(signals)} opportunities found", "arbitrage")
        for signal in signals[:3]:
            order = {
                "market_id": signal.market_id,
                "question": signal.market_question,
                "side": signal.side,
                "size": signal.size_usd,
                "price": signal.yes_price if signal.side == "buy_yes" else signal.no_price,
                "order_type": "LIMIT",
                "strategy": "arbitrage",
            }
            result = await self.executor.place_order(order)
            if result["status"] == "filled":
                self.airdrop.record_trade(signal.market_id, result["volume"], signal.actual_pnl, "LIMIT")
                self._arb_trades += 1
                self._arb_pnl += signal.actual_pnl
                self._record_trade(result, signal.actual_pnl)
                self.logs.append(
                    "TRADE",
                    f"[ARB] {signal.side} ${signal.size_usd:.1f} dev={signal.deviation:.3f} pnl={signal.actual_pnl:+.4f}",
                    "arbitrage",
                )

    async def _run_market_maker(self, markets: list[dict]):
        quotes = self.mm_engine.run(markets, self.risk)
        if not quotes:
            return
        self.logs.append("SIGNAL", f"[MM] {len(quotes)} quotes generated", "market_maker")
        for quote in quotes[:5]:
            order = {
                "market_id": quote.market_id,
                "question": quote.market_question,
                "side": "bid" if quote.bid_filled else "ask",
                "size": quote.fill_size,
                "price": quote.bid_price if quote.bid_filled else quote.ask_price,
                "order_type": "LIMIT",
                "strategy": "market_maker",
            }
            result = await self.executor.place_order(order)
            if result["status"] == "filled":
                self.airdrop.record_trade(quote.market_id, result["volume"], quote.pnl, "LIMIT")
                self._mm_trades += 1
                self._mm_pnl += quote.pnl
                self._record_trade(result, quote.pnl)
                self.logs.append(
                    "TRADE",
                    f"[MM] spread={quote.spread:.3f} size=${quote.fill_size:.1f} pnl={quote.pnl:+.4f}",
                    "market_maker",
                )

    async def _run_momentum(self, markets: list[dict]):
        signals = run_momentum(markets, self.risk)
        if not signals:
            return
        self.logs.append("SIGNAL", f"[MOM] {len(signals)} signals", "momentum")
        for signal in signals[:2]:
            order = {
                "market_id": signal.market_id,
                "question": signal.market_question,
                "side": "buy" if signal.direction == "long" else "sell",
                "size": signal.size_usd,
                "price": signal.entry_price,
                "order_type": "LIMIT",
                "strategy": "momentum",
            }
            result = await self.executor.place_order(order)
            if result["status"] == "filled":
                self.airdrop.record_trade(signal.market_id, result["volume"], signal.pnl, "LIMIT")
                self._mom_trades += 1
                self._mom_pnl += signal.pnl
                self._record_trade(result, signal.pnl)
                self.logs.append(
                    "TRADE",
                    f"[MOM] {signal.direction} ${signal.size_usd:.1f} chg={signal.price_change_pct:+.1f}% pnl={signal.pnl:+.4f}",
                    "momentum",
                )

    def _record_trade(self, result: dict, pnl: float):
        self._trades.append({
            "id": result.get("order_id", str(uuid.uuid4())),
            "market_id": result.get("market_id", ""),
            "question": result.get("question", ""),
            "side": result.get("side", ""),
            "size": result.get("size", 0),
            "price": result.get("filled_price", 0),
            "pnl": round(pnl, 4),
            "strategy": result.get("strategy", ""),
            "status": result.get("status", ""),
            "timestamp": result.get("timestamp", datetime.utcnow().isoformat()),
        })
        if len(self._trades) > 500:
            self._trades = self._trades[-500:]

    def get_trades(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._trades))[:limit]

    def get_logs(self, limit: int = 40) -> list[dict]:
        return self.logs.tail(limit)

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "paused": self._paused,
            "cycle_count": self._cycle_count,
            "markets_scanned": self._markets_scanned,
            "total_trades": len(self._trades),
            "strategies": {
                "arbitrage": {"trades": self._arb_trades, "pnl": round(self._arb_pnl, 4)},
                "market_maker": {"trades": self._mm_trades, "pnl": round(self._mm_pnl, 4)},
                "momentum": {"trades": self._mom_trades, "pnl": round(self._mom_pnl, 4)},
            },
            "risk": self.risk.get_status(),
            "airdrop_score": self.airdrop.overall_score(),
        }


# Singleton instance
bot = BotEngine()
