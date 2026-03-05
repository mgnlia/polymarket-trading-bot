"""
Async client for Polymarket Gamma API.
https://gamma-api.polymarket.com — no auth required.
"""
from __future__ import annotations

import httpx

from .config import settings


async def fetch_markets(limit: int = 50, active: bool = True) -> list[dict]:
    """Fetch active markets from Gamma API."""
    if settings.SIMULATION_MODE:
        return _simulated_markets()

    params: dict = {"limit": limit, "active": str(active).lower()}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{settings.GAMMA_API_URL}/markets", params=params)
        resp.raise_for_status()
        return resp.json()


def _simulated_markets() -> list[dict]:
    """Return a set of fake markets for simulation mode."""
    return [
        {
            "id": f"sim-market-{i}",
            "question": q,
            "category": cat,
            "outcomes": ["Yes", "No"],
            "outcomePrices": [str(yes), str(round(1 - yes, 2))],
            "volume": v,
            "active": True,
        }
        for i, (q, cat, yes, v) in enumerate(
            [
                ("Will BTC exceed $100k by June 2026?", "crypto", 0.62, 450000),
                ("Will the US have a recession in 2026?", "politics", 0.35, 320000),
                ("Champions League winner: Man City?", "sports", 0.28, 180000),
                ("Will GPT-5 be released by March 2026?", "science", 0.55, 210000),
                ("Next UK PM from Labour?", "world", 0.48, 95000),
                ("Oscar Best Picture: sci-fi film?", "entertainment", 0.15, 62000),
                ("ETH above $5k by Q2 2026?", "crypto", 0.40, 380000),
                ("US inflation below 3% Dec 2025?", "politics", 0.58, 275000),
                ("NBA MVP 2026: Luka Doncic?", "sports", 0.22, 150000),
                ("Will DOGE reach $1?", "crypto", 0.08, 520000),
                ("India GDP growth > 7%?", "world", 0.42, 88000),
                ("Taylor Swift #1 album 2026?", "entertainment", 0.65, 72000),
            ]
        )
    ]
