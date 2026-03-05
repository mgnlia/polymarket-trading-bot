"""Configuration with environment variable support."""
from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    # API Keys
    private_key: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    api_passphrase: Optional[str] = None
    bot_api_key: Optional[str] = None  # BOT_API_KEY — protects all non-health endpoints

    # Mode
    simulation_mode: bool = True
    chain_id: int = 137  # Polygon

    # Endpoints
    gamma_api_url: str = "https://gamma-api.polymarket.com"
    clob_api_url: str = "https://clob.polymarket.com"
    ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    # Strategy config
    arb_threshold: float = 0.02         # 2% mispricing to trigger arb
    mm_spread_min: float = 0.03         # 3c minimum spread for MM
    mm_order_size: float = 5.0          # USDC per MM order
    momentum_threshold: float = 0.60   # >60% confidence for momentum trade
    max_position_size: float = 50.0    # Max USDC per position
    max_positions: int = 10
    daily_loss_limit: float = 100.0
    max_drawdown_pct: float = 0.20      # 20% peak-to-trough drawdown halts trading

    # Kelly criterion
    kelly_fraction: float = 0.25        # Fractional Kelly (quarter-Kelly for safety)

    # Airdrop targets
    markets_target: int = 50
    volume_target: float = 10000.0      # USDC

    # Bot timing
    cycle_interval: int = 30            # seconds
    market_refresh_interval: int = 300  # 5 min

    # DB
    db_url: str = "sqlite+aiosqlite:///./data/polymarket.db"

    # CORS
    cors_origins: List[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
