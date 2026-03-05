"""Tests for BOT_API_KEY authentication middleware."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from app.auth import require_api_key


@pytest.mark.asyncio
async def test_no_key_configured_allows_all():
    """If BOT_API_KEY not set, all requests pass through."""
    request = MagicMock()
    with patch("app.auth.settings") as mock_settings:
        mock_settings.bot_api_key = None
        await require_api_key(request)  # Should not raise


@pytest.mark.asyncio
async def test_valid_key_passes():
    request = MagicMock()
    request.headers = {"Authorization": "Bearer secret123"}
    with patch("app.auth.settings") as mock_settings:
        mock_settings.bot_api_key = "secret123"
        await require_api_key(request)  # Should not raise


@pytest.mark.asyncio
async def test_invalid_key_raises_401():
    request = MagicMock()
    request.headers = {"Authorization": "Bearer wrongkey"}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    with patch("app.auth.settings") as mock_settings:
        mock_settings.bot_api_key = "secret123"
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(request)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_key_raises_401():
    request = MagicMock()
    request.headers = {}
    request.client = MagicMock()
    with patch("app.auth.settings") as mock_settings:
        mock_settings.bot_api_key = "secret123"
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(request)
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_x_bot_api_key_header_accepted():
    request = MagicMock()
    request.headers = {"X-Bot-Api-Key": "secret123"}
    with patch("app.auth.settings") as mock_settings:
        mock_settings.bot_api_key = "secret123"
        await require_api_key(request)  # Should not raise
