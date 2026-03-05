"""
Authentication middleware — BOT_API_KEY bearer token.
Uses secrets.compare_digest to prevent timing attacks.
"""
import secrets
import logging
from fastapi import Request, HTTPException, status

from .config import settings

logger = logging.getLogger(__name__)


def _get_token_from_request(request: Request) -> str | None:
    """Extract bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):]
    # Also accept X-Bot-Api-Key header
    return request.headers.get("X-Bot-Api-Key")


async def require_api_key(request: Request) -> None:
    """
    FastAPI dependency: validates BOT_API_KEY on protected endpoints.
    Raises 401 if key missing or invalid.
    Skips check if BOT_API_KEY is not configured (dev convenience).
    """
    configured_key = settings.bot_api_key
    if not configured_key:
        # No key configured — skip auth (dev/sim mode convenience)
        return

    provided_key = _get_token_from_request(request)
    if not provided_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key — provide 'Authorization: Bearer <key>' or 'X-Bot-Api-Key' header",
        )

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(provided_key.encode(), configured_key.encode()):
        logger.warning(f"[Auth] Invalid API key attempt from {request.client.host if request.client else 'unknown'}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
