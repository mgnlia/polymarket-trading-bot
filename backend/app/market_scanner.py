"""Market scanner — fetches and caches live markets from Gamma API."""
import asyncio
import logging
import random
from typing import Optional
from datetime import datetime, timedelta
import httpx

from .config import settings

logger = logging.getLogger(__name__)

# In-memory market cache
_markets: list[dict] = []
_last_refresh: Optional[datetime] = None
_CACHE_TTL = timedelta(seconds=settings.market_refresh_interval)


def _sim_markets(n: int = 60) -> list[dict]:
    """Generate realistic simulated markets for demo mode."""
    categories = ["politics", "crypto", "sports", "finance", "science", "entertainment"]
    questions = [
        "Will BTC exceed $100k by end of 2025?",
        "Will ETH reach $5k in 2025?",
        "Will the Fed cut rates in Q3 2025?",
        "Will Trump win the 2024 election?",
        "Will the S&P 500 end 2025 above 6000?",
        "Will Apple release AR glasses in 2025?",
        "Will OpenAI release GPT-5 in 2025?",
        "Will the US enter recession in 2025?",
        "Will Solana flip Ethereum by market cap?",
        "Will DOGE reach $1 in 2025?",
        "Will there be a US government shutdown in 2025?",
        "Will Elon Musk remain Twitter/X CEO through 2025?",
        "Will FIFA World Cup 2026 be held in US?",
        "Will AI replace 10% of jobs by 2026?",
        "Will gold reach $3000/oz in 2025?",
        "Will Netflix gain subscribers in Q2 2025?",
        "Will China invade Taiwan in 2025?",
        "Will NVIDIA stock double in 2025?",
        "Will a new COVID variant cause lockdowns?",
        "Will Polymarket reach $1B monthly volume?",
    ]

    markets = []
    for i in range(n):
        yes = round(random.uniform(0.1, 0.9), 3)
        no = round(random.uniform(0.05, min(0.95, 1 - yes + 0.15)), 3)
        spread = round(abs(1.0 - yes - no) + random.uniform(0, 0.05), 3)
        arb = (yes + no) < 0.97  # arbitrage if sum < 0.97
        markets.append({
            "condition_id": f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
            "question": questions[i % len(questions)] + (f" (#{i+1})" if i >= len(questions) else ""),
            "yes_price": yes,
            "no_price": no,
            "volume": round(random.uniform(1000, 500000), 0),
            "spread": spread,
            "arb_opportunity": arb,
            "category": random.choice(categories),
            "end_date": (datetime.utcnow() + timedelta(days=random.randint(1, 180))).isoformat(),
        })
    return markets


async def _fetch_gamma_markets(limit: int = 100) -> list[dict]:
    """Fetch markets from Gamma API."""
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(
                f"{settings.gamma_api_url}/markets",
                params={"limit": limit, "active": "true", "closed": "false"},
            )
            r.raise_for_status()
            data = r.json()
            markets = data if isinstance(data, list) else data.get("markets", [])

            result = []
            for m in markets:
                try:
                    tokens = m.get("tokens", [])
                    yes_price = float(tokens[0].get("price", 0.5)) if tokens else 0.5
                    no_price = float(tokens[1].get("price", 0.5)) if len(tokens) > 1 else 1 - yes_price
                    spread = abs(1.0 - yes_price - no_price)
                    result.append({
                        "condition_id": m.get("conditionId", m.get("condition_id", "")),
                        "question": m.get("question", ""),
                        "yes_price": yes_price,
                        "no_price": no_price,
                        "volume": float(m.get("volume", 0)),
                        "spread": spread,
                        "arb_opportunity": (yes_price + no_price) < 0.97,
                        "category": m.get("category", ""),
                        "end_date": m.get("endDate", m.get("end_date", "")),
                    })
                except Exception:
                    continue
            return result
        except Exception as e:
            logger.warning(f"Gamma API fetch failed: {e}, using simulation")
            return []


async def refresh_markets(force: bool = False) -> list[dict]:
    """Refresh market cache, respecting TTL."""
    global _markets, _last_refresh

    now = datetime.utcnow()
    if not force and _last_refresh and (now - _last_refresh) < _CACHE_TTL and _markets:
        return _markets

    if settings.simulation_mode:
        _markets = _sim_markets(60)
        logger.info(f"[Scanner] Simulation: loaded {len(_markets)} markets")
    else:
        live = await _fetch_gamma_markets(100)
        if live:
            _markets = live
            logger.info(f"[Scanner] Fetched {len(_markets)} live markets from Gamma API")
        else:
            # Fall back to simulation if API fails
            _markets = _sim_markets(60)
            logger.warning("[Scanner] Using simulated markets (API fallback)")

    _last_refresh = now
    return _markets


def get_cached_markets() -> list[dict]:
    return _markets


def get_arb_opportunities() -> list[dict]:
    return [m for m in _markets if m.get("arb_opportunity")]


def get_mm_candidates(min_spread: float = 0.03) -> list[dict]:
    return [m for m in _markets if m.get("spread", 0) >= min_spread]


async def get_orderbook(token_id: str) -> dict:
    """Get orderbook for a token (simulated or live)."""
    if settings.simulation_mode:
        mid = random.uniform(0.3, 0.7)
        spread = random.uniform(0.01, 0.05)
        return {
            "bids": [{"price": round(mid - spread/2 - i*0.01, 3), "size": round(random.uniform(10, 100), 1)} for i in range(5)],
            "asks": [{"price": round(mid + spread/2 + i*0.01, 3), "size": round(random.uniform(10, 100), 1)} for i in range(5)],
            "mid": mid,
            "spread": spread,
        }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(f"{settings.clob_api_url}/book", params={"token_id": token_id})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Orderbook fetch failed for {token_id}: {e}")
            return {}
