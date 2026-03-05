"""
Bot Engine — orchestrates all strategies, executor, risk, and airdrop tracking.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from .airdrop import AirdropOptimizer
from .config import settings
from .executor import OrderExecutor
from .market_scanner import refresh_markets
from .risk import RiskManager
from .strategies import (
    AntiSybilScheduler,
    DiversityFarmer,
    MarketMakerEngine,
    run_momentum,
    scan_arb_opportunities,
)

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
        self.diversity_farmer = DiversityFarmer()
        self.anti_sybil = AntiSybilScheduler()

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
        self._div_trades = 0
        self._div_pnl = 0.0
        self._anti_sybil_skips = 0

        mode = "SIMULATION" if settings.simulation_mode else "LIVE"
        self.logs.append(
            "INFO",
            f"Bot engine initialized | Mode: {mode} | Strategies: ARB + MM + Momentum + Diversity",
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

    async def scan_markets(self, force: bool = True) -> list[dict]:
        """Refresh markets and return latest snapshot (used by /bot/scan endpoint)."""
        markets = await refresh_markets(force=force)
        self._markets_scanned = len(markets)
        self.logs.append("INFO", f"Market scan complete | markets={len(markets)} force={force}")
        return markets

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

        markets = await self.scan_markets(force=False)

        if not markets:
            self.logs.append("WARN", "No markets available — skipping cycle")
            return

        await self._run_arbitrage(markets)
        await self._run_market_maker(markets)
        await self._run_momentum(markets)
        await self._run_diversity(markets)

        self.logs.append(
            "INFO",
            f"Cycle #{cycle_id} complete | Trades: {len(self._trades)} | "
            f"Airdrop: {self.airdrop.overall_score():.0f}/100",
        )

    async def _execute_order(self, order: dict, strategy: str, fallback_pnl: float = 0.0) -> Optional[dict]:
        """
        Unified execution wrapper.
        - Applies anti-sybil scheduling (should_trade_now, humanize_order, record_trade)
        - Performs runtime risk accounting (open before send, close after fill)
        """
        can_trade_now, gate_reason = self.anti_sybil.should_trade_now()
        if not can_trade_now:
            if settings.simulation_mode:
                self.logs.append(
                    "INFO",
                    f"[{strategy.upper()}] AntiSybil gate: {gate_reason} | simulation override",
                    strategy,
                )
            else:
                self._anti_sybil_skips += 1
                self.logs.append("WARN", f"[{strategy.upper()}] Skipped by AntiSybil: {gate_reason}", strategy)
                return None

        humanized_order = self.anti_sybil.humanize_order(order)
        size = float(humanized_order.get("size", 0.0))

        allowed, reason = self.risk.can_trade(size)
        if not allowed:
            self.logs.append("WARN", f"[{strategy.upper()}] Risk blocked order: {reason}", strategy)
            return None

        # Runtime risk accounting before order placement (required)
        self.risk.record_order_open(size)
        result = await self.executor.place_order(humanized_order)

        if result.get("status") == "filled":
            pnl = float(result.get("pnl", fallback_pnl))
            volume = float(result.get("volume", 0.0))
            # Runtime risk accounting after filled order (required)
            self.risk.record_order_close(size, pnl=pnl, volume=volume)
            self.anti_sybil.record_trade()
            result["_realized_pnl"] = pnl
            return result

        # Avoid leaking open position count for pending/cancelled simulated orders
        self.risk.record_order_close(size, pnl=0.0, volume=0.0)
        return result

    async def _run_arbitrage(self, markets: list[dict]):
        signals = scan_arb_opportunities(markets, self.risk)
        if not signals:
            return

        self.logs.append("SIGNAL", f"[ARB] {len(signals)} opportunities found", "arbitrage")
        for signal in signals[:3]:
            order = {
                "market_id": signal.market_id,
                "question": signal.market_question,
                "side": "BUY" if signal.side == "buy_yes" else "SELL",
                "size": signal.size_usd,
                "price": signal.yes_price if signal.side == "buy_yes" else signal.no_price,
                "order_type": "LIMIT",
                "strategy": "arbitrage",
                "expected_edge": signal.deviation * 100,
            }

            result = await self._execute_order(order, strategy="arbitrage", fallback_pnl=signal.actual_pnl)
            if not result or result.get("status") != "filled":
                continue

            realized_pnl = float(result.get("_realized_pnl", signal.actual_pnl))
            volume = float(result.get("volume", 0.0))

            self.airdrop.record_trade(signal.market_id, volume, realized_pnl, "LIMIT")
            self._arb_trades += 1
            self._arb_pnl += realized_pnl
            self._record_trade(result, realized_pnl)
            self.logs.append(
                "TRADE",
                (
                    f"[ARB] {signal.side} ${signal.size_usd:.1f} dev={signal.deviation:.3f} "
                    f"pnl={realized_pnl:+.4f}"
                ),
                "arbitrage",
            )

    async def _run_market_maker(self, markets: list[dict]):
        quotes = self.mm_engine.run(markets, self.risk)
        if not quotes:
            return

        self.logs.append("SIGNAL", f"[MM] {len(quotes)} quotes generated", "market_maker")
        for quote in quotes[:5]:
            side = "BUY" if quote.bid_filled else "SELL"
            price = quote.bid_price if quote.bid_filled else quote.ask_price
            order = {
                "market_id": quote.market_id,
                "question": quote.market_question,
                "side": side,
                "size": quote.fill_size,
                "price": price,
                "order_type": "LIMIT",
                "strategy": "market_maker",
                "expected_spread": quote.spread,
            }

            result = await self._execute_order(order, strategy="market_maker", fallback_pnl=quote.pnl)
            if not result or result.get("status") != "filled":
                continue

            realized_pnl = float(result.get("_realized_pnl", quote.pnl))
            volume = float(result.get("volume", 0.0))

            self.airdrop.record_trade(quote.market_id, volume, realized_pnl, "LIMIT")
            self._mm_trades += 1
            self._mm_pnl += realized_pnl
            self._record_trade(result, realized_pnl)
            self.logs.append(
                "TRADE",
                (
                    f"[MM] spread={quote.spread:.3f} size=${quote.fill_size:.1f} "
                    f"pnl={realized_pnl:+.4f}"
                ),
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
                "side": "BUY" if signal.direction == "long" else "SELL",
                "size": signal.size_usd,
                "price": signal.entry_price,
                "order_type": "LIMIT",
                "strategy": "momentum",
                "confidence": max(0.1, min(0.9, 0.5 + abs(signal.price_change_pct) / 200)),
            }

            result = await self._execute_order(order, strategy="momentum", fallback_pnl=signal.pnl)
            if not result or result.get("status") != "filled":
                continue

            realized_pnl = float(result.get("_realized_pnl", signal.pnl))
            volume = float(result.get("volume", 0.0))

            self.airdrop.record_trade(signal.market_id, volume, realized_pnl, "LIMIT")
            self._mom_trades += 1
            self._mom_pnl += realized_pnl
            self._record_trade(result, realized_pnl)
            self.logs.append(
                "TRADE",
                (
                    f"[MOM] {signal.direction} ${signal.size_usd:.1f} "
                    f"chg={signal.price_change_pct:+.1f}% pnl={realized_pnl:+.4f}"
                ),
                "momentum",
            )

    async def _run_diversity(self, markets: list[dict]):
        signals = self.diversity_farmer.scan(markets)
        if not signals:
            return

        cap = 6
        selected = signals[:cap]
        self.logs.append(
            "SIGNAL",
            f"[DIVERSITY] {len(signals)} opportunities | executing {len(selected)} (cap={cap})",
            "diversity",
        )

        for signal in selected:
            order = self.diversity_farmer.generate_order(signal)
            result = await self._execute_order(order, strategy="diversity", fallback_pnl=0.0)
            if not result or result.get("status") != "filled":
                continue

            realized_pnl = float(result.get("_realized_pnl", 0.0))
            volume = float(result.get("volume", 0.0))

            self.airdrop.record_trade(signal.market_id, volume, realized_pnl, order.get("order_type", "LIMIT"))
            self.diversity_farmer.record_trade(signal.market_id, signal.category, realized_pnl, volume)
            self._div_trades += 1
            self._div_pnl += realized_pnl
            self._record_trade(result, realized_pnl)
            self.logs.append(
                "TRADE",
                (
                    f"[DIVERSITY] {signal.category} size=${order['size']:.2f} "
                    f"gain={signal.diversity_score_gain:.2f} pnl={realized_pnl:+.4f}"
                ),
                "diversity",
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
                "diversity": {"trades": self._div_trades, "pnl": round(self._div_pnl, 4)},
            },
            "anti_sybil": {
                "skipped_orders": self._anti_sybil_skips,
                **self.anti_sybil.get_stats(),
            },
            "diversity": self.diversity_farmer.get_stats(),
            "risk": self.risk.get_status(),
            "airdrop_score": self.airdrop.overall_score(),
            "executor": self.executor.get_stats(),
        }


# Singleton instance
bot = BotEngine()
