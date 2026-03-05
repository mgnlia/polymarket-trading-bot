"""
Polymarket Trading Bot — FastAPI Backend
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse  # noqa: F401
from sse_starlette.sse import EventSourceResponse

from .auth import require_api_key
from .config import settings
from .bot_engine import bot
from .market_scanner import refresh_markets, get_cached_markets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: pre-load markets."""
    logger.info("🚀 Polymarket Bot API starting up")
    try:
        await refresh_markets()
        logger.info(f"Pre-loaded {len(get_cached_markets())} markets")
    except Exception as e:
        logger.warning(f"Market pre-load failed: {e}")
    yield
    bot.stop()
    logger.info("Bot API shut down")


app = FastAPI(
    title="Polymarket Trading Bot API",
    version="1.0.0",
    description="Multi-strategy Polymarket trading bot with airdrop optimization",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health (no auth) ────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ─── Status (no auth — dashboard reads this) ─────────────────────────────────

@app.get("/status")
async def get_status():
    return {
        "ok": True,
        "simulation_mode": settings.simulation_mode,
        "bot": bot.get_status(),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─── Bot Controls (auth required) ────────────────────────────────────────────

@app.post("/bot/start")
async def start_bot(_: str = Depends(require_api_key)):
    bot.start()
    return {"ok": True, "message": "Bot started"}


@app.post("/bot/stop")
async def stop_bot(_: str = Depends(require_api_key)):
    bot.stop()
    return {"ok": True, "message": "Bot stopped"}


@app.post("/bot/pause")
async def pause_bot(_: str = Depends(require_api_key)):
    bot.pause()
    return {"ok": True, "paused": bot.paused}


@app.post("/bot/cycle")
async def run_cycle(_: str = Depends(require_api_key)):
    """Manually trigger one trading cycle."""
    await bot.run_cycle_once()
    return {"ok": True, "message": "Cycle complete", "trades": len(bot.get_trades(10))}


@app.post("/bot/scan")
async def scan_markets(_: str = Depends(require_api_key)):
    """Force refresh market data."""
    markets = await bot.scan_markets()
    return {"ok": True, "markets_found": len(markets)}


# ─── Data Endpoints (auth required) ──────────────────────────────────────────

@app.get("/trades")
async def get_trades(
    limit: int = Query(50, ge=1, le=500),
    _: str = Depends(require_api_key),
):
    trades = bot.get_trades(limit)
    total_pnl = sum(t.get("pnl", 0) for t in trades)
    return {
        "trades": trades,
        "count": len(trades),
        "total_pnl": round(total_pnl, 4),
    }


@app.get("/markets")
async def get_markets(limit: int = Query(30, ge=1, le=200)):
    markets = get_cached_markets()
    return {
        "markets": markets[:limit],
        "total": len(markets),
    }


@app.get("/airdrop")
async def get_airdrop(_: str = Depends(require_api_key)):
    return bot.airdrop.get_report()


@app.get("/logs")
async def get_logs(
    limit: int = Query(40, ge=1, le=200),
    _: str = Depends(require_api_key),
):
    logs = bot.get_logs(limit)
    return {"logs": logs, "count": len(logs)}


# ─── SSE Stream (no auth — dashboard polling) ────────────────────────────────

async def _status_generator() -> AsyncGenerator[dict, None]:
    """Generate SSE events with bot status."""
    while True:
        try:
            status = bot.get_status()
            recent_logs = bot.get_logs(10)
            yield {
                "event": "status",
                "data": json.dumps({
                    "bot": status,
                    "recent_logs": recent_logs,
                    "timestamp": datetime.utcnow().isoformat(),
                }),
            }
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
        await asyncio.sleep(3)


@app.get("/stream")
async def stream_status():
    """SSE endpoint for real-time bot status updates."""
    return EventSourceResponse(_status_generator())
