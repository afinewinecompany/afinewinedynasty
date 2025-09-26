from typing import Any, Dict, List, Optional, Union
from pydantic import AnyHttpUrl, BaseSettings, PostgresDsn, validator


class Settings(BaseSettings):
    PROJECT_NAME: str = "A Fine Wine Dynasty API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # CORS Origins - restrict in production
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1"]

    @validator("BACKEND_CORS_ORIGINS", pre=True)
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

    @validator("SQLALCHEMY_DATABASE_URI", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            user=values.get("POSTGRES_USER"),
            password=values.get("POSTGRES_PASSWORD"),
            host=values.get("POSTGRES_SERVER"),
            port=values.get("POSTGRES_PORT"),
            path=f"/{values.get('POSTGRES_DB') or ''}",
        )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "6xt6IjjwkEH4lIQiiW-lS5PX7GXYd-YBNp3PF5Jls64"
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

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()