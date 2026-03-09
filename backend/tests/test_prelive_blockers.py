"""Regression tests for pre-live blockers around MM simulation parsing and risk accounting."""
from unittest.mock import AsyncMock, patch

import pytest

from app.bot_engine import BotEngine
from app.risk import RiskManager
from app.strategies.arbitrage import ArbSignal
from app.strategies.market_maker import MarketMakerEngine


def test_market_maker_generates_signal_for_yes_no_sim_market():
    engine = MarketMakerEngine()
    risk = RiskManager()
    markets = [
        {
            "condition_id": "sim-mm-1",
            "question": "Will the simulation market emit an MM quote?",
            "yes_price": 0.61,
            "no_price": 0.39,
        }
    ]

    with (
        patch("app.strategies.market_maker.random.random", side_effect=[0.0, 1.0]),
        patch("app.strategies.market_maker.random.gauss", return_value=0.0),
        patch("app.strategies.market_maker.random.uniform", return_value=1.0),
    ):
        signals = engine.run(markets, risk)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.market_id == "sim-mm-1"
    assert signal.market_question == "Will the simulation market emit an MM quote?"
    assert signal.bid_filled is True
    assert signal.ask_filled is False
    assert signal.fill_size >= 0.25


@pytest.mark.asyncio
async def test_market_maker_execution_updates_risk_once(monkeypatch):
    engine = BotEngine()
    counters = {"open": 0, "close": 0}
    markets = [
        {
            "condition_id": "sim-mm-2",
            "question": "Will MM execution mutate risk exactly once?",
            "yes_price": 0.58,
            "no_price": 0.42,
        }
    ]

    def record_open(size: float):
        counters["open"] += 1

    def record_close(size: float, pnl: float, volume: float):
        counters["close"] += 1

    async def fake_place_order(order: dict) -> dict:
        return {
            "order_id": "filled-mm-order",
            "status": "filled",
            "filled_price": order["price"],
            "size": order["size"],
            "pnl": 1.25,
            "volume": order["size"] * order["price"],
            "timestamp": "2026-03-01T00:00:00",
            "market_id": order["market_id"],
            "question": order.get("question", ""),
            "side": order["side"],
            "strategy": order["strategy"],
        }

    monkeypatch.setattr(engine.anti_sybil, "should_trade_now", lambda: (True, "ok"))
    monkeypatch.setattr(engine.anti_sybil, "humanize_order", lambda order: order)
    monkeypatch.setattr(engine.anti_sybil, "record_trade", lambda: None)
    monkeypatch.setattr(engine.risk, "record_order_open", record_open)
    monkeypatch.setattr(engine.risk, "record_order_close", record_close)
    monkeypatch.setattr(engine.executor, "place_order", AsyncMock(side_effect=fake_place_order))

    with (
        patch("app.strategies.market_maker.random.random", side_effect=[0.0, 1.0]),
        patch("app.strategies.market_maker.random.gauss", return_value=0.0),
        patch("app.strategies.market_maker.random.uniform", return_value=1.0),
    ):
        await engine._run_market_maker(markets)

    assert counters == {"open": 1, "close": 1}
    assert engine.get_status()["strategies"]["market_maker"]["trades"] == 1


@pytest.mark.asyncio
async def test_arbitrage_execution_updates_risk_once(monkeypatch):
    engine = BotEngine()
    counters = {"open": 0, "close": 0}

    def record_open(size: float):
        counters["open"] += 1

    def record_close(size: float, pnl: float, volume: float):
        counters["close"] += 1

    async def fake_place_order(order: dict) -> dict:
        return {
            "order_id": "filled-arb-order",
            "status": "filled",
            "filled_price": order["price"],
            "size": order["size"],
            "pnl": 0.75,
            "volume": order["size"] * order["price"],
            "timestamp": "2026-03-01T00:00:00",
            "market_id": order["market_id"],
            "question": order.get("question", ""),
            "side": order["side"],
            "strategy": order["strategy"],
        }

    monkeypatch.setattr(engine.anti_sybil, "should_trade_now", lambda: (True, "ok"))
    monkeypatch.setattr(engine.anti_sybil, "humanize_order", lambda order: order)
    monkeypatch.setattr(engine.anti_sybil, "record_trade", lambda: None)
    monkeypatch.setattr(engine.risk, "record_order_open", record_open)
    monkeypatch.setattr(engine.risk, "record_order_close", record_close)
    monkeypatch.setattr(engine.executor, "place_order", AsyncMock(side_effect=fake_place_order))

    signal = ArbSignal(
        market_id="sim-arb-1",
        market_question="Will arbitrage execution mutate risk exactly once?",
        yes_price=0.40,
        no_price=0.50,
        deviation=0.10,
        side="buy_yes",
        size_usd=10.44,
        expected_pnl=1.044,
        actual_pnl=0.944,
        executed=True,
    )
    monkeypatch.setattr("app.bot_engine.scan_arb_opportunities", lambda markets, risk: [signal])

    await engine._run_arbitrage([
        {
            "condition_id": "sim-arb-1",
            "question": signal.market_question,
            "yes_price": 0.40,
            "no_price": 0.50,
        }
    ])

    assert counters == {"open": 1, "close": 1}
    assert engine.get_status()["strategies"]["arbitrage"]["trades"] == 1
