"""Async HTTP client wrappers for Polymarket APIs."""
from __future__ import annotations

import httpx

from backend.config import settings

GAMMA_URL = settings.GAMMA_API_URL
DATA_URL = settings.DATA_API_URL
CLOB_URL = settings.CLOB_API_URL


async def fetch_markets(limit: int = 100, offset: int = 0) -> list[dict]:
    """Fetch active markets from Gamma API."""
    params = {"limit": limit, "offset": offset, "active": "true", "closed": "false"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{GAMMA_URL}/markets", params=params)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        return data.get("markets", [])


async def fetch_market_orderbook(token_id: str) -> dict:
    """Fetch order book from CLOB API."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{CLOB_URL}/book", params={"token_id": token_id})
        r.raise_for_status()
        return r.json()


async def fetch_market_price(token_id: str) -> dict:
    """Fetch midpoint price for a token."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{CLOB_URL}/midpoint", params={"token_id": token_id})
        r.raise_for_status()
        return r.json()


async def fetch_prices_history(token_id: str, interval: str = "1d") -> list[dict]:
    """Fetch price history from CLOB API."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{CLOB_URL}/prices-history",
            params={"token_id": token_id, "interval": interval, "fidelity": 60},
        )
        r.raise_for_status()
        return r.json().get("history", [])


async def fetch_positions(address: str) -> list[dict]:
    """Fetch positions from Data API."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{DATA_URL}/positions", params={"user": address})
        r.raise_for_status()
        return r.json()


async def fetch_trade_history(address: str, limit: int = 50) -> list[dict]:
    """Fetch trade history from Data API."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{DATA_URL}/activity",
            params={"user": address, "limit": limit},
        )
        r.raise_for_status()
        return r.json()
