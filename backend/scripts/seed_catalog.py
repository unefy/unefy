"""Populate the global catalog (sports, units, disciplines) with initial data.

Idempotent: existing rows are left untouched, only missing ones are inserted.

This used to run on every application start. It no longer does — the catalog
is master data maintained by platform admins, and re-seeding on boot would
resurrect entries an admin deliberately removed. Run it once on a fresh
database, or later to top up after adding new entries to the seed files.

Run inside the backend container:
    uv run python scripts/seed_catalog.py
"""

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.discipline_seeds import DISCIPLINES
from app.database import async_session_factory
from app.models.discipline import Discipline
from app.models.sport import Sport

# The seeded disciplines are all German shooting-sport entries (DSB/BDS).
SEED_SPORT_KEY = "shooting"


async def _seed_disciplines(session: AsyncSession) -> int:
    sport = (
        await session.execute(select(Sport).where(Sport.key == SEED_SPORT_KEY))
    ).scalar_one_or_none()
    if sport is None:
        print(f"Sport {SEED_SPORT_KEY!r} is missing — run migrations first (mise run migrate).")
        return 0

    existing = set((await session.execute(select(Discipline.slug))).scalars().all())

    inserted = 0
    for entry in DISCIPLINES:
        if entry["slug"] in existing:
            continue
        session.add(Discipline(id=uuid.uuid4(), sport_id=sport.id, **entry))
        inserted += 1

    return inserted


async def main() -> None:
    async with async_session_factory() as session:
        sports = (await session.execute(select(Sport))).scalars().all()
        print(f"Sports present: {', '.join(s.key for s in sports) or 'none'}")

        inserted = await _seed_disciplines(session)
        await session.commit()

    total = len(DISCIPLINES)
    if inserted:
        print(f"Inserted {inserted} of {total} catalog disciplines.")
    else:
        print(f"Catalog already complete ({total} disciplines).")


if __name__ == "__main__":
    asyncio.run(main())
