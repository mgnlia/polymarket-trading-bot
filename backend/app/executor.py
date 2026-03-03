"""
Order Executor
Handles order placement — simulation or live via py-clob-client.
"""
import logging
import random
import uuid
from datetime import datetime
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)


class SimulatedFill:
    """Simulates order fills with realistic behavior."""

    def __init__(self):
        self.fill_rate = 0.72  # 72% of limit orders fill in sim
        self.slippage_bps = 5  # 5 bps average slippage

    def should_fill(self, order_type: str) -> bool:
        if order_type == "MARKET":
            return True
        return random.random() < self.fill_rate

    def fill_price(self, price: float, side: str) -> float:
        slippage = price * self.slippage_bps / 10000
        if side == "BUY":
            return price + slippage
        return price - slippage


class OrderExecutor:
    """
    Executes orders either in simulation or via py-clob-client.
    """

    def __init__(self):
        self.sim = SimulatedFill()
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
        if settings.simulation_mode:
            return await self._sim_order(order)
        return await self._live_order(order)

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
        else:
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
        strategy = order.get("strategy", "")
        size = order["size"]

        if strategy == "arbitrage":
            edge = order.get("expected_edge", 2.0) / 100
            return round(size * edge * random.uniform(0.5, 1.2), 4)
        elif strategy == "market_maker":
            spread = order.get("expected_spread", 0.03)
            return round(size * spread * 0.5 * random.uniform(0.3, 1.0), 4)
        elif strategy == "momentum":
            confidence = order.get("confidence", 0.6)
            win = random.random() < confidence
            if win:
                return round(size * random.uniform(0.05, 0.30), 4)
            else:
                return round(-size * random.uniform(0.02, 0.15), 4)
        return round(random.uniform(-0.01, 0.05) * size, 4)

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
        if self._orders == 0:
            return 0.0
        return (self._fills / self._orders) * 100

    def get_stats(self) -> dict:
        return {
            "orders_placed": self._orders,
            "fills": self._fills,
            "fill_rate": round(self.fill_rate, 2),
            "total_volume": round(self._total_volume, 2),
        }
