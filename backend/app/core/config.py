from pydantic_settings import BaseSettings
from typing import List
from pydantic import field_validator
import os


class Settings(BaseSettings):
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    # Database Configuration
    # Database: PostgreSQL only (required)
    database_url: str | None = None
    
    # API Configuration
    secret_key: str = "your-secret-key-here"
    jwt_secret: str = "your-jwt-secret-here"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 360
    jwt_refresh_token_expire_days: int = 7
    cors_origins: str = os.getenv("CORS_ORIGINS", f"http://localhost:{os.getenv('FRONTEND_PORT', '3100')},https://yourdomain.com")
    api_host: str = "0.0.0.0"
    api_port: int = int(os.getenv("API_PORT", "3102"))
    
    # External APIs
    binance_api_url: str = "https://api.binance.com/api/v3"
    # Note: Binance API keys are now stored per-user in encrypted format
    # Global keys are no longer used for security reasons
    currency_api_url: str = "https://api.exchangerate-api.com/v4/latest/USD"
    telegram_api_url: str = "https://api.telegram.org/bot"
    
    # AI Advisor Configuration
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4")
    news_api_key: str = os.getenv("NEWS_API_KEY", "")
    ai_prediction_interval_hours: int = int(os.getenv("AI_PREDICTION_INTERVAL_HOURS", "24"))
    ai_prediction_batch_size: int = int(os.getenv("AI_PREDICTION_BATCH_SIZE", "1"))
    openrouter_api_url: str = "https://openrouter.ai/api/v1"
    news_api_url: str = "https://newsapi.org/v2"
    
    # Price Update Configuration
    price_update_interval_seconds: int = int(os.getenv("PRICE_UPDATE_INTERVAL_SECONDS", "300"))  # 5 minutes
    
    # Redis (optional, for caching/session)
    redis_url: str | None = None
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    # Performance Configuration
    max_connections: int = 20
    price_cache_duration: int = 60
    currency_cache_duration: int = 1800
    
    # Database Connection Pooling
    db_pool_size: int = 20
    db_max_overflow: int = 30
    db_pool_recycle: int = 3600
    db_pool_pre_ping: bool = True
    
    # Debug Configuration
    debug: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    
    # Logging Configuration
    log_level: str = "DEBUG" if debug else "INFO"
    log_file: str = "logs/crypto_agent.log"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Frontend Configuration
    frontend_refresh_interval: int = 60000
    
    # Script Configuration
    backend_port: int = int(os.getenv("API_PORT", "3102"))
    frontend_port: int = int(os.getenv("FRONTEND_PORT", "3100"))
    log_dir: str = "logs"
    data_dir: str = "data"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins string to list"""
        return [origin.strip() for origin in self.cors_origins.split(',')]

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables


# Create settings instance
settings = Settings()
