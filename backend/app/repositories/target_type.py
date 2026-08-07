from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.target_type import TargetType


class TargetTypeRepository:
    """Read access to the global target catalog.

    Not tenant-scoped: ring geometry is defined by the sport federations, not by
    a club. Written only by the seeder.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all(self, *, include_inactive: bool = False) -> list[TargetType]:
        query = select(TargetType).order_by(TargetType.distance_m, TargetType.name)
        if not include_inactive:
            query = query.where(TargetType.is_active.is_(True))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str) -> TargetType | None:
        """Look up by slug, including inactive rows.

        Inactive ones are still resolvable on purpose: a target can be
        deactivated after entries were recorded against it, and those entries
        must stay re-scoreable.
        """
        result = await self.session.execute(select(TargetType).where(TargetType.slug == slug))
        return result.scalar_one_or_none()
