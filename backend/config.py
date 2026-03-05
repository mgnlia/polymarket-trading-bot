"""Configuration settings for the Polymarket Trading Bot."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Auth
    BOT_API_KEY: str = ""

    # Wallet (for live trading)
    PRIVATE_KEY: str = ""
    POLYMARKET_ADDRESS: str = ""

    # Mode
    SIMULATION_MODE: bool = True

    # Risk
    MAX_DRAWDOWN_PCT: float = 0.15
    DAILY_LOSS_CAP_USD: float = 100.0
    MAX_POSITION_USD: float = 50.0
    KELLY_FRACTION: float = 0.25

    # Strategy toggles
    ENABLE_ARBITRAGE: bool = True
    ENABLE_MARKET_MAKING: bool = True
    ENABLE_MOMENTUM: bool = True
    ENABLE_DIVERSITY: bool = True

    # API endpoints
    CLOB_API_URL: str = "https://clob.polymarket.com"
    GAMMA_API_URL: str = "https://gamma-api.polymarket.com"
    DATA_API_URL: str = "https://data-api.polymarket.com"
    WS_URL: str = "wss://ws-subscriptions-clob.polymarket.com/ws/"

    class Config:
        env_file = ".env"


settings = Settings()
