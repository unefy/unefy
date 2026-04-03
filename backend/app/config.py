from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "unefy"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # API
    API_V1_PREFIX: str = "/api/v1"
    API_PUBLIC_V1_PREFIX: str = "/api/public/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://unefy:unefy@localhost:5432/unefy"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Deployment
    DEPLOYMENT_MODE: Literal["self-hosted", "saas"] = "self-hosted"

    # Security
    INTERNAL_API_SECRET: str = "change-me-in-production"
    SESSION_SECRET: str = "change-me-in-production"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Web App (for OAuth redirect after login)
    WEB_APP_URL: str = "http://localhost:3008"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3008"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
