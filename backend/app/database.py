from collections.abc import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.events.outbox import publish, register_change_listener, take_pending
from app.redis import get_redis

logger = structlog.get_logger()

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG,
)

# Installed once, here, because every session in the process comes from this
# module. See app/events/outbox.py for why collection is a listener rather than a
# call in each write path.
register_change_listener()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """A session per request, committed on the way out.

    Change hints queued during the request are published *after* the commit
    returns — see `app/events/outbox.py` for why the ordering is load-bearing.
    On the exception path they go away with the transaction, which is the correct
    pairing: no commit, no notification.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            logger.exception("database_session_error")
            await session.rollback()
            raise

        # Deliberately outside the try: a failure here must not be mistaken for a
        # database error, and `publish` swallows its own exceptions anyway.
        pending = take_pending(session)
        if pending:
            await publish(get_redis(), pending)
