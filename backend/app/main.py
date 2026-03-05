"""
Polymarket Trading Bot — FastAPI Backend
Auth: BOT_API_KEY bearer token on all non-health endpoints (secrets.compare_digest).
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from .config import settings
from .auth import require_api_key
from .bot_engine import bot
from .market_scanner import refresh_markets, get_cached_markets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Polymarket Bot API starting up")
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
    version="2.0.0",
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


# ─── Status (auth required) ──────────────────────────────────────────────────

@app.get("/status", dependencies=[Depends(require_api_key)])
async def get_status():
    return {
        "ok": True,
        "simulation_mode": settings.simulation_mode,
        "bot": bot.get_status(),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─── Bot Controls (auth required) ────────────────────────────────────────────

@app.post("/bot/start", dependencies=[Depends(require_api_key)])
async def start_bot():
    bot.start()
    return {"ok": True, "message": "Bot started"}


@app.post("/bot/stop", dependencies=[Depends(require_api_key)])
async def stop_bot():
    bot.stop()
    return {"ok": True, "message": "Bot stopped"}


@app.post("/bot/pause", dependencies=[Depends(require_api_key)])
async def pause_bot():
    bot.pause()
    return {"ok": True, "paused": bot.paused}


@app.post("/bot/cycle", dependencies=[Depends(require_api_key)])
async def run_cycle():
    await bot.run_cycle_once()
    return {"ok": True, "message": "Cycle complete", "trades": len(bot.get_trades(10))}


@app.post("/bot/scan", dependencies=[Depends(require_api_key)])
async def scan_markets():
    markets = await bot.scan_markets()
    return {"ok": True, "markets_found": len(markets)}


# ─── Data Endpoints (auth required) ──────────────────────────────────────────

@app.get("/trades", dependencies=[Depends(require_api_key)])
async def get_trades(limit: int = Query(50, ge=1, le=500)):
    trades = bot.get_trades(limit)
    total_pnl = sum(t.get("pnl", 0) for t in trades)
    return {"trades": trades, "count": len(trades), "total_pnl": round(total_pnl, 4)}


@app.get("/markets", dependencies=[Depends(require_api_key)])
async def get_markets(limit: int = Query(30, ge=1, le=200)):
    markets = get_cached_markets()
    return {"markets": markets[:limit], "total": len(markets)}


@app.get("/airdrop", dependencies=[Depends(require_api_key)])
async def get_airdrop():
    return bot.airdrop.get_report()


@app.get("/logs", dependencies=[Depends(require_api_key)])
async def get_logs(limit: int = Query(40, ge=1, le=200)):
    logs = bot.get_logs(limit)
    return {"logs": logs, "count": len(logs)}


# ─── SSE Stream (auth required) ──────────────────────────────────────────────

async def _status_generator() -> AsyncGenerator[dict, None]:
    while True:
        try:
            yield {
                "event": "status",
                "data": json.dumps({
                    "bot": bot.get_status(),
                    "recent_logs": bot.get_logs(10),
                    "timestamp": datetime.utcnow().isoformat(),
                }),
            }
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
        await asyncio.sleep(3)


@app.get("/stream", dependencies=[Depends(require_api_key)])
async def stream_status():
    return EventSourceResponse(_status_generator())
