"""
Bot Engine — orchestrates all strategies, executor, risk, and airdrop tracking.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from .config import settings
from .strategies import ArbitrageStrategy, MarketMakerStrategy, MomentumStrategy
from .executor import OrderExecutor
from .risk import RiskManager
from .airdrop import AirdropOptimizer
from .market_scanner import refresh_markets, get_cached_markets

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
        self.arb = ArbitrageStrategy()
        self.mm = MarketMakerStrategy()
        self.momentum = MomentumStrategy()
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

        self.logs.append("INFO", "🚀 Bot engine initialized")
        self.logs.append(
            "INFO",
            f"Mode: {'SIMULATION' if settings.simulation_mode else 'LIVE'} | "
            f"Strategies: ARB + MM + Momentum"
        )
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
        self.logs.append("SUCCESS", "▶ Bot started — running all strategies")
        logger.info("[Bot] Started")

    def stop(self):
        self._running = False
        self._paused = False
        if self._task:
            self._task.cancel()
            self._task = None
        self.logs.append("INFO", "⏹ Bot stopped")
        logger.info("[Bot] Stopped")

    def pause(self):
        self._paused = not self._paused
        status = "paused" if self._paused else "resumed"
        self.logs.append("INFO", f"⏸ Bot {status}")
        logger.info(f"[Bot] {status.capitalize()}")

    async def run_cycle_once(self):
        await self._cycle()

    async def scan_markets(self):
        markets = await refresh_markets(force=True)
        self._markets_scanned = len(markets)
        self.logs.append("INFO", f"🔍 Scanned {len(markets)} markets")
        return markets

    async def _run_loop(self):
        self.logs.append("INFO", f"⏱ Cycle interval: {settings.cycle_interval}s")
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
        self.logs.append("INFO", f"⚡ Cycle #{cycle_id} starting")

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
            f"✅ Cycle #{cycle_id} complete | "
            f"Trades: {len(self._trades)} | "
            f"Airdrop: {self.airdrop.overall_score():.0f}/100"
        )

    async def _run_arbitrage(self, markets: list[dict]):
        signals = self.arb.scan(markets)
        if not signals:
            return
        self.logs.append("SIGNAL", f"[ARB] {len(signals)} opportunities found", "arbitrage")
        for signal in signals[:3]:
            orders = self.arb.generate_orders(signal)
            for order in orders:
                ok, reason = self.risk.can_trade(order["size"])
                if not ok:
                    self.logs.append("WARN", f"[ARB] Blocked: {reason}", "arbitrage")
                    continue
                result = await self.executor.place_order(order)
                if result["status"] == "filled":
                    self.risk.record_order_open(order["size"])
                    self.risk.record_order_close(order["size"], result["pnl"], result["volume"])
                    self.arb.record_trade(result["pnl"])
                    self.airdrop.record_trade(order["market_id"], result["volume"], result["pnl"], "LIMIT")
                    self._record_trade(result)
                    self.logs.append(
                        "TRADE",
                        f"[ARB] Filled {order['side']} {order['size']:.1f} @ {result['filled_price']:.4f} pnl={result['pnl']:+.4f}",
                        "arbitrage"
                    )

    async def _run_market_maker(self, markets: list[dict]):
        quotes = self.mm.scan(markets)
        if not quotes:
            return
        quotes = quotes[:5]
        self.logs.append("SIGNAL", f"[MM] {len(quotes)} quotes generated", "market_maker")
        for quote in quotes:
            orders = self.mm.generate_orders(quote)
            for order in orders:
                ok, reason = self.risk.can_trade(order["size"])
                if not ok:
                    continue
                result = await self.executor.place_order(order)
                if result["status"] == "filled":
                    self.risk.record_order_open(order["size"])
                    self.risk.record_order_close(order["size"], result["pnl"], result["volume"])
                    self.mm.record_fill(quote.expected_spread)
                    self.airdrop.record_trade(order["market_id"], result["volume"], result["pnl"], "LIMIT")
                    self._record_trade(result)
                    self.logs.append(
                        "TRADE",
                        f"[MM] {order['side']} {order['size']:.1f} @ {result['filled_price']:.4f} spread={quote.expected_spread:.3f} pnl={result['pnl']:+.4f}",
                        "market_maker"
                    )

    async def _run_momentum(self, markets: list[dict]):
        signals = self.momentum.scan(markets)
        if not signals:
            return
        signals = signals[:2]
        self.logs.append("SIGNAL", f"[MOM] {len(signals)} signals", "momentum")
        for signal in signals:
            order = self.momentum.generate_order(signal)
            ok, reason = self.risk.can_trade(order["size"])
            if not ok:
                self.logs.append("WARN", f"[MOM] Blocked: {reason}", "momentum")
                continue
            result = await self.executor.place_order(order)
            if result["status"] == "filled":
                self.risk.record_order_open(order["size"])
                self.risk.record_order_close(order["size"], result["pnl"], result["volume"])
                correct = result["pnl"] > 0
                self.momentum.record_trade(correct, result["pnl"])
                self.airdrop.record_trade(order["market_id"], result["volume"], result["pnl"], "LIMIT")
                self._record_trade(result)
                self.logs.append(
                    "TRADE",
                    f"[MOM] {signal.direction} {order['size']:.1f} @ {result['filled_price']:.4f} conf={signal.confidence:.2f} pnl={result['pnl']:+.4f}",
                    "momentum"
                )

    def _record_trade(self, result: dict):
        self._trades.append({
            "id": result.get("order_id", str(uuid.uuid4())),
            "market_id": result["market_id"],
            "question": result.get("question", ""),
            "side": result["side"],
            "size": result["size"],
            "price": result.get("filled_price", 0),
            "pnl": result["pnl"],
            "strategy": result["strategy"],
            "status": result["status"],
            "timestamp": result["timestamp"],
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
                "arbitrage": self.arb.get_stats(),
                "market_maker": self.mm.get_stats(),
                "momentum": self.momentum.get_stats(),
            },
            "risk": self.risk.get_status(),
            "executor": self.executor.get_stats(),
            "airdrop_score": self.airdrop.overall_score(),
        }


# Singleton instance
bot = BotEngine()
