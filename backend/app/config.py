from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sentinel value used in .env.example — must NOT reach production.
PLACEHOLDER_SECRET = "change-me-in-production"
MIN_SECRET_LENGTH = 32


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

    # Security — required in production, see validators below.
    INTERNAL_API_SECRET: str = PLACEHOLDER_SECRET
    SESSION_SECRET: str = PLACEHOLDER_SECRET

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # URLs
    BACKEND_URL: str = "http://localhost:8008"  # Public URL of the backend (for OAuth redirects)
    COOKIE_DOMAIN: str | None = None  # e.g. ".unefy.app" for cross-subdomain cookies
    WEB_APP_URL: str = "http://localhost:3008"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3008"]

    @field_validator("INTERNAL_API_SECRET", "SESSION_SECRET")
    @classmethod
    def _validate_secret_length(cls, value: str, info) -> str:  # type: ignore[no-untyped-def]
        # In DEBUG mode we allow the placeholder so `docker compose up` works
        # out of the box, but the secret must still be non-empty.
        if not value:
            raise ValueError(f"{info.field_name} must not be empty")
        return value

    @model_validator(mode="after")
    def _require_real_secrets_when_not_debug(self) -> "Settings":
        if self.DEBUG:
            return self
        problems: list[str] = []
        for name in ("INTERNAL_API_SECRET", "SESSION_SECRET"):
            value = getattr(self, name)
            if value == PLACEHOLDER_SECRET:
                problems.append(f"{name} is still set to the placeholder value")
            if len(value) < MIN_SECRET_LENGTH:
                problems.append(f"{name} must be at least {MIN_SECRET_LENGTH} characters")
        if problems:
            joined = "; ".join(problems)
            raise ValueError(
                f"Production secret configuration invalid: {joined}. "
                "Set DEBUG=true for local development or provide real secrets."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
