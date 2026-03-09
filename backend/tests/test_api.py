"""API smoke tests aligned to the current FastAPI surface."""
from fastapi.testclient import TestClient

from app.bot_engine import bot
from app.config import settings
from app.main import app


client = TestClient(app)


def teardown_function():
    bot.stop()
    settings.bot_api_key = None


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


def test_status_endpoint_exposes_bot_state():
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "simulation_mode" in data
    assert "bot" in data
    assert "risk" in data["bot"]
    assert "executor" in data["bot"]


def test_markets_endpoint_returns_list():
    response = client.get("/markets?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "markets" in data
    assert isinstance(data["markets"], list)
    assert data["total"] >= 0


def test_protected_endpoint_allows_access_without_configured_api_key():
    settings.bot_api_key = None
    response = client.get("/trades")
    assert response.status_code == 200
    data = response.json()
    assert "trades" in data
    assert "count" in data


def test_protected_endpoint_requires_api_key_when_configured():
    settings.bot_api_key = "secret-token"

    missing = client.get("/logs")
    assert missing.status_code == 401
    assert "Missing API key" in missing.text

    wrong = client.get("/logs", headers={"Authorization": "Bearer wrong-token"})
    assert wrong.status_code == 401
    assert "Invalid API key" in wrong.text

    valid = client.get("/logs", headers={"Authorization": "Bearer secret-token"})
    assert valid.status_code == 200
    payload = valid.json()
    assert "logs" in payload
    assert "count" in payload


def test_x_bot_api_key_header_is_supported():
    settings.bot_api_key = "secret-token"
    response = client.get("/airdrop", headers={"X-Bot-Api-Key": "secret-token"})
    assert response.status_code == 200
    data = response.json()
    assert "scores" in data
    assert "metrics" in data
