"""
WebSocket client for Polymarket real-time orderbook feed.
Connects to wss://ws-subscriptions-clob.polymarket.com/ws/market
and maintains a local orderbook cache keyed by asset_id (token_id).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Best-bid / best-ask snapshot per asset_id
_orderbook: dict[str, dict] = {}
_connected: bool = False
_ws_task: Optional[asyncio.Task] = None


def get_orderbook(asset_id: str) -> Optional[dict]:
    """Return the latest orderbook snapshot for an asset, or None."""
    return _orderbook.get(asset_id)


def get_best_bid(asset_id: str) -> Optional[float]:
    book = _orderbook.get(asset_id)
    if not book:
        return None
    bids = book.get("bids", [])
    return float(bids[0]["price"]) if bids else None


def get_best_ask(asset_id: str) -> Optional[float]:
    book = _orderbook.get(asset_id)
    if not book:
        return None
    asks = book.get("asks", [])
    return float(asks[0]["price"]) if asks else None


def is_connected() -> bool:
    return _connected


def _apply_book_update(msg: dict) -> None:
    """Parse a Polymarket WS message and update the local orderbook cache."""
    event_type = msg.get("event_type") or msg.get("type", "")
    asset_id = msg.get("asset_id") or msg.get("market", "")
    if not asset_id:
        return

    if event_type in ("book", "price_change"):
        # Full snapshot or incremental update
        bids = msg.get("bids", [])
        asks = msg.get("asks", [])
        # Sort: bids descending, asks ascending
        bids_sorted = sorted(bids, key=lambda x: float(x.get("price", 0)), reverse=True)
        asks_sorted = sorted(asks, key=lambda x: float(x.get("price", 1)))
        _orderbook[asset_id] = {
            "asset_id": asset_id,
            "bids": bids_sorted[:10],
            "asks": asks_sorted[:10],
            "timestamp": msg.get("timestamp") or datetime.utcnow().isoformat(),
        }
    elif event_type == "last_trade_price":
        if asset_id in _orderbook:
            _orderbook[asset_id]["last_trade_price"] = msg.get("price")


async def _run_ws(
    asset_ids: list[str],
    on_update: Optional[Callable[[str, dict], None]] = None,
    reconnect_delay: float = 5.0,
) -> None:
    """
    Internal coroutine: connects, subscribes, and processes messages.
    Reconnects automatically on disconnect.
    """
    global _connected
    try:
        import websockets  # type: ignore[import]
    except ImportError:
        logger.error("[WS] websockets package not installed — pip install websockets")
        return

    subscribe_msg = json.dumps({
        "auth": {},
        "type": "subscribe",
        "markets": asset_ids,
    })

    while True:
        try:
            logger.info(f"[WS] Connecting to {WS_URL} for {len(asset_ids)} assets")
            async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=10) as ws:
                _connected = True
                await ws.send(subscribe_msg)
                logger.info("[WS] Subscribed — listening for orderbook updates")
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        # Polymarket may send a list of events or a single event
                        events = msg if isinstance(msg, list) else [msg]
                        for event in events:
                            _apply_book_update(event)
                            aid = event.get("asset_id") or event.get("market", "")
                            if on_update and aid:
                                on_update(aid, _orderbook.get(aid, {}))
                    except Exception as parse_err:
                        logger.debug(f"[WS] Parse error: {parse_err}")
        except Exception as conn_err:
            _connected = False
            logger.warning(f"[WS] Disconnected: {conn_err} — reconnecting in {reconnect_delay}s")
            await asyncio.sleep(reconnect_delay)


def start_ws(
    asset_ids: list[str],
    on_update: Optional[Callable[[str, dict], None]] = None,
) -> asyncio.Task:
    """
    Start the WebSocket listener as a background asyncio task.
    Returns the Task so callers can cancel it on shutdown.

    Usage:
        task = start_ws(["0xabc...", "0xdef..."])
        # later:
        task.cancel()
    """
    global _ws_task
    if _ws_task and not _ws_task.done():
        logger.info("[WS] Already running — returning existing task")
        return _ws_task
    _ws_task = asyncio.create_task(_run_ws(asset_ids, on_update))
    logger.info(f"[WS] Background task started for {len(asset_ids)} assets")
    return _ws_task


def stop_ws() -> None:
    """Cancel the WebSocket background task."""
    global _ws_task, _connected
    if _ws_task and not _ws_task.done():
        _ws_task.cancel()
        logger.info("[WS] Task cancelled")
    _connected = False
    _ws_task = None
