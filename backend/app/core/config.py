from pydantic_settings import BaseSettings
from typing import List
from pydantic import field_validator
import os


class Settings(BaseSettings):
    # Database Configuration (SQLite)
    database_file: str = "data/crypto_portfolio.db"
    
    # API Configuration
    secret_key: str = "your-secret-key-here"
    jwt_secret: str = "your-jwt-secret-here"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:3000,https://yourdomain.com"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # External APIs
    binance_api_url: str = "https://api.binance.com/api/v3"
    currency_api_url: str = "https://api.exchangerate-api.com/v4/latest/USD"
    telegram_api_url: str = "https://api.telegram.org/bot"
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
    
    # Logging Configuration
    log_level: str = "INFO"
    log_file: str = "logs/crypto_agent.log"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Frontend Configuration
    frontend_refresh_interval: int = 30000
    
    # Script Configuration
    backend_port: int = 8000
    frontend_port: int = 3000
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
