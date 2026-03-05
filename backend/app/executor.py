"""
Order Executor — simulation or live via py-clob-client.

Simulation PnL is realistic: all strategies can generate losses.
Market Maker uses MMInventory for paired fill logic and net position tracking.
"""
import logging
import random
import uuid
from datetime import datetime
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)


class MMInventory:
    """
    Tracks market-maker net inventory per market.
    Bid and ask fills are paired — realizes PnL when a position closes.
    Prevents accumulation of unhedged directional exposure without tracking.
    """

    def __init__(self):
        self._positions: dict[str, float] = {}   # market_id -> net position
        self._avg_prices: dict[str, float] = {}  # market_id -> average entry price

    def record_fill(self, market_id: str, side: str, size: float, price: float) -> float:
        """Record fill; return realized PnL from any paired (closing) fill."""
        current_pos = self._positions.get(market_id, 0.0)
        current_avg = self._avg_prices.get(market_id, 0.0)
        realized_pnl = 0.0
        delta = size if side == "BUY" else -size
        new_pos = current_pos + delta

        if current_pos != 0 and ((current_pos > 0) != (delta > 0)):
            closing_size = min(abs(current_pos), abs(delta))
            if current_pos > 0:
                realized_pnl = closing_size * (price - current_avg)
            else:
                realized_pnl = closing_size * (current_avg - price)

        if new_pos == 0:
            self._avg_prices.pop(market_id, None)
            self._positions[market_id] = 0.0
        elif abs(new_pos) > abs(current_pos):
            total_cost = abs(current_pos) * current_avg + abs(delta) * price
            self._avg_prices[market_id] = total_cost / abs(new_pos)
            self._positions[market_id] = new_pos
        else:
            self._positions[market_id] = new_pos

        return round(realized_pnl, 6)

    def total_exposure(self) -> float:
        return sum(abs(v) for v in self._positions.values())


class SimulatedFill:
    def __init__(self):
        self.fill_rate = 0.72
        self.slippage_bps = 5

    def should_fill(self, order_type: str) -> bool:
        return True if order_type == "MARKET" else random.random() < self.fill_rate

    def fill_price(self, price: float, side: str) -> float:
        slippage = price * self.slippage_bps / 10000
        return min(1.0, price + slippage) if side == "BUY" else max(0.0, price - slippage)


class OrderExecutor:
    def __init__(self):
        self.sim = SimulatedFill()
        self.mm_inventory = MMInventory()
        self.client = None
        self._fills = 0
        self._orders = 0
        self._total_volume = 0.0

        if not settings.simulation_mode:
            self._init_live_client()
        else:
            logger.info("[Executor] Running in SIMULATION mode")

    def _init_live_client(self):
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds
            creds = ApiCreds(
                api_key=settings.api_key or "",
                api_secret=settings.api_secret or "",
                api_passphrase=settings.api_passphrase or "",
            )
            self.client = ClobClient(
                host=settings.clob_api_url,
                chain_id=settings.chain_id,
                private_key=settings.private_key,
                creds=creds,
            )
            logger.info("[Executor] Live CLOB client initialized")
        except Exception as e:
            logger.error(f"[Executor] Failed to init live client: {e}. Falling back to simulation.")
            settings.simulation_mode = True

    async def place_order(self, order: dict) -> dict:
        self._orders += 1
        return await self._sim_order(order) if settings.simulation_mode else await self._live_order(order)

    async def _sim_order(self, order: dict) -> dict:
        filled = self.sim.should_fill(order.get("order_type", "LIMIT"))
        fill_price = self.sim.fill_price(order["price"], order["side"])
        if filled:
            self._fills += 1
            volume = order["size"] * fill_price
            self._total_volume += volume
            pnl = self._calc_sim_pnl(order, fill_price)
            return {
                "order_id": f"sim_{uuid.uuid4().hex[:12]}",
                "status": "filled",
                "filled_price": fill_price,
                "size": order["size"],
                "pnl": pnl,
                "volume": volume,
                "timestamp": datetime.utcnow().isoformat(),
                "market_id": order["market_id"],
                "question": order.get("question", ""),
                "side": order["side"],
                "strategy": order["strategy"],
            }
        return {
            "order_id": f"sim_{uuid.uuid4().hex[:12]}",
            "status": "pending",
            "filled_price": None,
            "size": order["size"],
            "pnl": 0.0,
            "volume": 0.0,
            "timestamp": datetime.utcnow().isoformat(),
            "market_id": order["market_id"],
            "question": order.get("question", ""),
            "side": order["side"],
            "strategy": order["strategy"],
        }

    def _calc_sim_pnl(self, order: dict, fill_price: float) -> float:
        """Realistic PnL — all strategies can lose money."""
        strategy = order.get("strategy", "")
        size = order["size"]

        if strategy == "arbitrage":
            edge = order.get("expected_edge", 2.0) / 100
            # 70% capture edge, 30% adverse selection
            if random.random() < 0.70:
                return round(size * edge * random.uniform(0.3, 1.0), 4)
            return round(-size * edge * random.uniform(0.1, 0.5), 4)

        elif strategy == "market_maker":
            # Use inventory tracking for paired fills
            realized = self.mm_inventory.record_fill(
                order["market_id"], order["side"], size, fill_price
            )
            if realized != 0:
                return round(realized, 4)
            # Opening inventory position — normally distributed inventory risk
            spread = order.get("expected_spread", 0.03)
            inventory_risk = random.gauss(0, spread * 0.8)
            return round(size * inventory_risk * 0.5, 4)

        elif strategy == "momentum":
            confidence = order.get("confidence", 0.6)
            win = random.random() < confidence
            return round(size * random.uniform(0.05, 0.30), 4) if win else round(-size * random.uniform(0.02, 0.20), 4)

        elif strategy in ("diversity", "anti_sybil"):
            outcome = random.gauss(0.005, 0.04)
            return round(size * outcome, 4)

        return round(random.gauss(0, 0.02) * size, 4)

    async def _live_order(self, order: dict) -> dict:
        try:
            from py_clob_client.clob_types import OrderArgs
            order_args = OrderArgs(
                token_id=order["market_id"],
                price=order["price"],
                size=order["size"],
                side=order["side"],
            )
            result = self.client.create_and_post_order(order_args)
            self._fills += 1
            self._total_volume += order["size"] * order["price"]
            return {
                "order_id": result.get("orderID", ""),
                "status": result.get("status", "pending"),
                "filled_price": order["price"],
                "size": order["size"],
                "pnl": 0.0,
                "volume": order["size"] * order["price"],
                "timestamp": datetime.utcnow().isoformat(),
                "market_id": order["market_id"],
                "question": order.get("question", ""),
                "side": order["side"],
                "strategy": order["strategy"],
            }
        except Exception as e:
            logger.error(f"[Executor] Live order failed: {e}")
            return {"status": "error", "error": str(e), "pnl": 0.0, "volume": 0.0}

    @property
    def fill_rate(self) -> float:
        return 0.0 if self._orders == 0 else (self._fills / self._orders) * 100

    def get_stats(self) -> dict:
        return {
            "orders_placed": self._orders,
            "fills": self._fills,
            "fill_rate": round(self.fill_rate, 2),
            "total_volume": round(self._total_volume, 2),
            "mm_inventory_exposure": round(self.mm_inventory.total_exposure(), 4),
        }
