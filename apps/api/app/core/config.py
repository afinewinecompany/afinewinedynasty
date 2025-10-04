from typing import Any, Dict, List, Optional, Union
from pydantic import AnyHttpUrl, PostgresDsn, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "A Fine Wine Dynasty API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # CORS Origins - restrict in production
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "healthcheck.railway.app", "*"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "afinewinedynasty"
    POSTGRES_PORT: str = "5432"
    SQLALCHEMY_DATABASE_URI: Optional[PostgresDsn] = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info) -> Any:
        if isinstance(v, str):
            # Railway and other PaaS providers give postgresql:// but we need postgresql+asyncpg://
            if v.startswith("postgresql://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
            return v
        values = info.data
        return f"postgresql+asyncpg://{values.get('POSTGRES_USER')}:{values.get('POSTGRES_PASSWORD')}@{values.get('POSTGRES_SERVER')}:{values.get('POSTGRES_PORT')}/{values.get('POSTGRES_DB')}"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str  # Must be set via environment variable - NEVER hardcode in production!
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds

    # Authentication Rate Limiting
    AUTH_RATE_LIMIT_ATTEMPTS: int = 5
    AUTH_RATE_LIMIT_WINDOW: int = 15 * 60  # 15 minutes in seconds

    # Sensitive Endpoints Rate Limiting
    SENSITIVE_RATE_LIMIT_ATTEMPTS: int = 3
    SENSITIVE_RATE_LIMIT_WINDOW: int = 60 * 60  # 1 hour in seconds

    # Google OAuth 2.0
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""
    GOOGLE_TOKEN_URL: str = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL: str = "https://www.googleapis.com/oauth2/v2/userinfo"

    # MLB Stats API
    MLB_STATS_API_BASE_URL: str = "https://statsapi.mlb.com/api/v1"
    MLB_STATS_API_RATE_LIMIT: int = 1000  # requests per day
    MLB_STATS_API_REQUEST_DELAY: float = 0.1  # seconds between requests

    # Fangraphs Configuration
    FANGRAPHS_BASE_URL: str = "https://www.fangraphs.com"
    FANGRAPHS_RATE_LIMIT_CALLS: int = 1  # requests per period
    FANGRAPHS_RATE_LIMIT_PERIOD: float = 1.0  # seconds
    FANGRAPHS_REQUEST_TIMEOUT: int = 30  # seconds
    FANGRAPHS_MAX_RETRIES: int = 3
    FANGRAPHS_USER_AGENT: str = "A Fine Wine Dynasty Bot 1.0"

    # Stripe Configuration
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PREMIUM_PRICE_ID: str = ""  # Monthly price ID for premium plan ($9.99)
    STRIPE_SUCCESS_URL: str = "http://localhost:3000/subscription/success"
    STRIPE_CANCEL_URL: str = "http://localhost:3000/subscription/cancel"

    # Fantrax Configuration
    FANTRAX_REDIRECT_URI: str = "http://localhost:3000/integrations/fantrax/callback"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Environment
    ENVIRONMENT: str = "development"

    model_config = {
        "case_sensitive": True,
        "env_file": ".env",
        "extra": "ignore"  # Allow extra fields in .env
    }


settings = Settings()