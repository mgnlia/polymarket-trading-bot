"""Tests for risk management — Kelly criterion, drawdown circuit breaker, daily loss limit."""
import pytest
from unittest.mock import patch
from app.risk import RiskManager


@pytest.fixture
def risk():
    with patch("app.risk.settings") as mock_settings:
        mock_settings.max_positions = 5
        mock_settings.max_position_size = 100.0
        mock_settings.daily_loss_limit = 50.0
        mock_settings.max_drawdown_pct = 0.20
        mock_settings.kelly_fraction = 0.25
        yield RiskManager()


def test_can_trade_ok(risk):
    ok, reason = risk.can_trade(10.0)
    assert ok
    assert reason == "ok"


def test_blocks_oversized_order(risk):
    ok, reason = risk.can_trade(200.0)
    assert not ok
    assert "exceeds max" in reason


def test_daily_loss_limit(risk):
    risk.state.daily_pnl = -60.0
    ok, reason = risk.can_trade(5.0)
    assert not ok
    assert "loss limit" in reason


def test_max_drawdown_circuit_breaker(risk):
    risk.state.peak_equity = 1000.0
    risk.state.current_equity = 750.0  # 25% drawdown > 20% limit
    ok, reason = risk.can_trade(5.0)
    assert not ok
    assert "drawdown" in reason.lower()


def test_drawdown_not_triggered_below_limit(risk):
    risk.state.peak_equity = 1000.0
    risk.state.current_equity = 850.0  # 15% drawdown < 20% limit
    ok, reason = risk.can_trade(5.0)
    assert ok


def test_kelly_size_positive(risk):
    size = risk.kelly_size(win_prob=0.6, win_pct=0.3, loss_pct=0.2)
    assert size > 0
    assert size <= 100.0


def test_kelly_size_zero_edge(risk):
    # p*b - q = 0 => no bet
    size = risk.kelly_size(win_prob=0.4, win_pct=0.2, loss_pct=0.3)
    assert size >= 0


def test_kelly_size_capped_at_max(risk):
    # Very high edge should still be capped
    size = risk.kelly_size(win_prob=0.99, win_pct=10.0, loss_pct=0.01)
    assert size <= 100.0


def test_max_positions_limit(risk):
    risk.state.open_positions = 5
    ok, reason = risk.can_trade(5.0)
    assert not ok
    assert "Max positions" in reason


def test_record_order_updates_equity(risk):
    risk.record_order_open(10.0)
    risk.record_order_close(10.0, pnl=5.0, volume=10.0)
    assert risk.state.current_equity == 5.0
    assert risk.state.peak_equity == 5.0


def test_drawdown_halts_after_close(risk):
    risk.state.peak_equity = 100.0
    risk.state.current_equity = 85.0  # 15% drawdown — ok
    risk.record_order_close(10.0, pnl=-20.0, volume=10.0)  # Now 35% drawdown
    assert risk.state.halted
    assert "drawdown" in risk.state.halt_reason.lower()
