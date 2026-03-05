"""
Async client for Polymarket Data API.
https://data-api.polymarket.com — no auth required.
"""
from __future__ import annotations

import httpx

from .config import settings


async def fetch_positions(address: str = "") -> list[dict]:
    """Fetch positions for an address from Data API."""
    if settings.SIMULATION_MODE:
        return []
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{settings.DATA_API_URL}/positions", params={"address": address})
        resp.raise_for_status()
        return resp.json()


async def fetch_trade_history(address: str = "", limit: int = 50) -> list[dict]:
    """Fetch trade history from Data API."""
    if settings.SIMULATION_MODE:
        return []
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{settings.DATA_API_URL}/trades",
            params={"address": address, "limit": limit},
        )
        resp.raise_for_status()
        return resp.json()
