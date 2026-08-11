from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

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
    JWT_SECRET: str = PLACEHOLDER_SECRET
    # Seeds for the rotating attendance code are derived from this rather than
    # stored, so rotating it invalidates every code currently on a phone. Its
    # own secret and not JWT_SECRET: the two have different lifetimes, and
    # rotating tokens should not lock every member out of checking in.
    ATTENDANCE_SECRET: str = PLACEHOLDER_SECRET

    # Mobile JWT lifetimes
    JWT_ACCESS_TTL_SECONDS: int = 900  # 15 min
    JWT_REFRESH_TTL_SECONDS: int = 2592000  # 30 days

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # Extra client ids whose ID tokens the mobile endpoint accepts, on top of
    # GOOGLE_CLIENT_ID. A self-hoster running the *published* app against their
    # own backend needs this: the app asks Credential Manager for a token for
    # the app's own server client id, which is not the operator's.
    GOOGLE_MOBILE_CLIENT_IDS: list[str] = []

    # URLs
    BACKEND_URL: str = "http://localhost:8008"  # Public URL of the backend (for OAuth redirects)
    COOKIE_DOMAIN: str | None = None  # e.g. ".unefy.app" for cross-subdomain cookies
    WEB_APP_URL: str = "http://localhost:3008"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3008"]

    # Email (SMTP). Without SMTP_HOST nothing is sent — messages are written to
    # the log instead, so local development works without a mail server and a
    # misconfigured deployment fails loudly in the log rather than silently.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "unefy <noreply@localhost>"
    SMTP_STARTTLS: bool = True

    # How long a magic link stays valid. Short by design: the link is a bearer
    # credential sitting in an inbox.
    MAGIC_LINK_TTL_SECONDS: int = 900  # 15 min

    # Push (FCM). Off by default: `docker compose up` must work without a
    # Google account. With PUSH_ENABLED and no credentials file the register
    # endpoints answer 503 with a clear code, and the fan-out task never starts.
    PUSH_ENABLED: bool = False
    # Path to the Firebase service-account JSON. This one *is* a secret — it
    # can send push to every device in every club.
    FCM_CREDENTIALS_FILE: str = ""

    # File storage (document library). A directory on disk is the default:
    # `docker compose up` must not require an object store for a club to file
    # its statutes. Point STORAGE_PATH at a volume — a path inside the
    # container is a document library that empties itself on every deploy.
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    STORAGE_PATH: str = "./var/storage"
    # Per file. Around what a twelve-page scan needs, with room to spare.
    MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024
    # Per club. Without a ceiling an upload form in a multi-tenant install is
    # an open hard disk, so the limit exists from the first version rather
    # than being retrofitted once one is full.
    TENANT_STORAGE_QUOTA_BYTES: int = 1024 * 1024 * 1024

    # RFC-3161 time-stamping authority for proof-chain anchors. Empty by
    # default: an unconfigured install has no anchors rather than fake ones —
    # the chain still holds against outsiders, only the external witness for
    # self-hosted operators is missing. (e.g. https://freetsa.org/tsr)
    TSA_URL: str = ""

    @field_validator("INTERNAL_API_SECRET", "SESSION_SECRET", "JWT_SECRET", "ATTENDANCE_SECRET")
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
        for name in ("INTERNAL_API_SECRET", "SESSION_SECRET", "JWT_SECRET", "ATTENDANCE_SECRET"):
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

    @model_validator(mode="after")
    def _refuse_a_storage_backend_that_does_not_exist(self) -> "Settings":
        """`s3` is a documented value with no implementation behind it yet.

        Accepting it would mean a deployment that believes its documents are
        in an object store while they are written to a container's filesystem
        — discovered on the first redeploy, when they are gone.
        """
        if self.STORAGE_BACKEND != "local":
            raise ValueError(
                f"STORAGE_BACKEND={self.STORAGE_BACKEND} is not implemented yet. "
                "Only 'local' works today; see docs/plans/document-library.md."
            )
        return self

    @model_validator(mode="after")
    def _require_a_cookie_domain_that_spans_both_hosts(self) -> "Settings":
        """A session cookie the app host cannot read is an unusable login.

        The magic link is redeemed on the backend host, which sets the session
        cookie and redirects to the app host. Without a `Domain` that covers
        both, the browser keeps the cookie for the backend alone: the app asks
        `/auth/me` without it, sees no session, and sends the user back to the
        login form having just proved who they are.

        Refused at startup rather than logged, because the failure is otherwise
        invisible from the outside — every request answers 200, the health
        checks pass, and only a human trying to sign in ever finds out.

        Not checked when either side is local: `WEB_APP_URL` left at its
        default is an install that does not serve the web app at all, and a
        mobile-only deployment must still boot.
        """
        if self.DEBUG:
            return self

        backend_host = _host_of(self.BACKEND_URL)
        app_host = _host_of(self.WEB_APP_URL)
        if not backend_host or not app_host:
            return self
        if _is_local(backend_host) or _is_local(app_host):
            return self
        if backend_host == app_host:
            return self

        domain = (self.COOKIE_DOMAIN or "").strip()
        if not domain:
            raise ValueError(
                f"BACKEND_URL ({backend_host}) and WEB_APP_URL ({app_host}) are different "
                "hosts, so COOKIE_DOMAIN must name their shared parent domain "
                f"(e.g. .{_shared_suffix(backend_host, app_host) or 'example.com'}). "
                "Without it the session cookie never reaches the app and no one can sign in."
            )
        if not (_covers(domain, backend_host) and _covers(domain, app_host)):
            raise ValueError(
                f"COOKIE_DOMAIN ({domain}) does not cover both BACKEND_URL "
                f"({backend_host}) and WEB_APP_URL ({app_host}). A cookie set for a "
                "domain the app host is not part of will never be sent back."
            )
        return self


def _host_of(url: str) -> str:
    """The hostname of a URL, without port. Empty when it is not parseable."""
    return (urlparse(url).hostname or "").lower()


def _is_local(host: str) -> bool:
    return host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".localhost")


def _covers(domain: str, host: str) -> bool:
    """Whether a cookie `Domain` would be sent to `host`.

    The leading dot is optional in RFC 6265 and ignored here. The boundary dot
    in the suffix check is not decoration: without it `unefy.app` would appear
    to cover `not-unefy.app`.
    """
    bare = domain.lstrip(".").lower()
    return bool(bare) and (host == bare or host.endswith(f".{bare}"))


def _shared_suffix(first: str, second: str) -> str:
    """The longest common parent of two hosts, for the error message."""
    a = first.split(".")
    b = second.split(".")
    common: list[str] = []
    for left, right in zip(reversed(a), reversed(b), strict=False):
        if left != right:
            break
        common.insert(0, left)
    # A single label is a public suffix, not a domain anyone may set a cookie
    # for — suggesting ".app" would be worse than suggesting nothing.
    return ".".join(common) if len(common) >= 2 else ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
