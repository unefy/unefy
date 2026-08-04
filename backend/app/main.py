import asyncio
import contextlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.middleware.logging import RequestLoggingMiddleware
from app.api.v1.router import router as v1_router
from app.api.verify import router as verify_router
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
            # Real attribute, just not re-exported from structlog.stdlib.
            structlog.stdlib.NAME_TO_LEVEL[log_level.lower()]  # type: ignore[attr-defined]
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
        # Re-raised, not swallowed. Serving on an un-migrated schema fails in
        # ways nobody connects back to this line: an endpoint 500s on a missing
        # column, or a query that should ride an index seq-scans the whole
        # tenant and the install just gets slower. A backend that will not start
        # is a problem someone fixes; one that starts wrong is one they live with.
        logger.error("migration_failed", error=str(e))
        raise


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    logger = structlog.get_logger()

    await run_migrations()

    await init_redis()
    logger.info("redis_connected")

    # The discipline catalog is *not* seeded here any more. It is now master
    # data maintained by platform admins through `/api/v1/admin/catalog/…`,
    # and re-running the seed on every boot would resurrect entries an admin
    # deliberately removed. Initial population happens once, in the migration
    # that introduced the catalog; `scripts/seed_catalog.py` can top it up.

    # Push fan-out, only when configured: `docker compose up` must work without
    # a Google account, and a bad credentials file must not stop the server —
    # it just does not push, loudly.
    push_task = None
    settings = get_settings()
    if settings.PUSH_ENABLED and settings.FCM_CREDENTIALS_FILE:
        import os

        from app.events.push_fanout import run_push_fanout
        from app.integrations.push import FcmSender
        from app.redis import get_redis

        try:
            sender = FcmSender(settings)
        except Exception as e:
            logger.error("push_fanout_not_started", error=str(e))
        else:
            consumer = f"{os.uname().nodename}-{os.getpid()}"
            push_task = asyncio.create_task(run_push_fanout(get_redis(), sender, consumer))
            logger.info("push_fanout_started", consumer=consumer)

    # Retention runs unconditionally — unlike push it needs no external account,
    # and a deployment that never deletes expired context rows is violating its
    # own privacy policy from day one.
    from app.redis import get_redis
    from app.tasks.retention import run_retention_loop

    retention_task = asyncio.create_task(run_retention_loop(get_redis()))
    logger.info("retention_loop_started")

    # Proof-chain anchoring, only with a configured TSA: an anchor without a
    # real external token would be a claim with nothing behind it.
    anchor_task = None
    if settings.TSA_URL:
        from app.integrations.tsa import TsaClient
        from app.tasks.proof_anchor import run_anchor_loop

        anchor_task = asyncio.create_task(run_anchor_loop(get_redis(), TsaClient(settings.TSA_URL)))
        logger.info("proof_anchor_loop_started", tsa=settings.TSA_URL)

    yield

    for task in (push_task, retention_task, anchor_task):
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

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
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            # BFF trust headers (Next.js → backend)
            "X-User-Id",
            "X-Tenant-Id",
            "X-Internal-Secret",
        ],
    )

    # SessionMiddleware for OAuth state (CSRF token during OAuth redirect flow)
    from starlette.middleware.sessions import SessionMiddleware

    app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET)
    # Inside the logging middleware (added after = runs first), so replays are
    # logged like any request; opt-in per request via the Idempotency-Key header.
    from app.api.middleware.idempotency import IdempotencyMiddleware

    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # Routers
    app.include_router(health_router)
    # Outside /api/v1 on purpose: the QR on a printed certificate carries this
    # URL, and a printed thing must outlive API versioning.
    app.include_router(verify_router)
    app.include_router(v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
