"""Seed the disciplines table with official DSB/BDS data.

Idempotent — skips existing slugs, updates nothing.
Called from app startup or as a management command.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.discipline_seeds import DISCIPLINES
from app.models.discipline import Discipline

logger = structlog.get_logger()


async def seed_disciplines(session: AsyncSession) -> int:
    """Insert missing disciplines. Returns count of newly inserted rows."""
    existing_slugs = set((await session.execute(select(Discipline.slug))).scalars().all())

    inserted = 0
    for entry in DISCIPLINES:
        if entry["slug"] in existing_slugs:
            continue
        session.add(Discipline(**entry))
        inserted += 1

    if inserted:
        await session.flush()
        logger.info("disciplines_seeded", count=inserted)

    return inserted
