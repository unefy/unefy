from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.middleware.logging import RequestLoggingMiddleware
from app.api.v1.router import router as v1_router
from app.config import get_settings
from app.core.exceptions import AppError, app_exception_handler, unhandled_exception_handler
from app.redis import close_redis, init_redis


def configure_logging(log_level: str) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.stdlib.NAME_TO_LEVEL[log_level.lower()]
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


async def run_migrations() -> None:
    """Run Alembic migrations on startup using async engine."""
    import structlog
    from alembic.config import Config

    from alembic import command

    logger = structlog.get_logger()

    try:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)
        # Run in thread to avoid blocking and async event loop issues
        import asyncio

        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
        logger.info("migrations_applied")
    except Exception as e:
        logger.error("migration_failed", error=str(e))


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    logger = structlog.get_logger()

    await run_migrations()

    await init_redis()
    logger.info("redis_connected")

    yield

    await close_redis()
    logger.info("redis_disconnected")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)

    app = FastAPI(
        title=settings.APP_NAME,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Exception handlers
    app.add_exception_handler(AppError, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Middleware (order matters — last added = first executed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # SessionMiddleware for OAuth state (CSRF token during OAuth redirect flow)
    from starlette.middleware.sessions import SessionMiddleware

    app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET)
    app.add_middleware(RequestLoggingMiddleware)

    # Routers
    app.include_router(health_router)
    app.include_router(v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
