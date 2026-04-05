from sqlalchemy import func, or_, select

from app.models.member import Member
from app.repositories.base import BaseRepository
from app.schemas.member import MemberCreate, MemberUpdate

# Allowlist of columns safe to sort by. Keys are the public sort names
# exposed in the API; values are the actual SQLAlchemy column attributes.
# Any sort_by input not in this map is ignored (falls back to last_name).
SORTABLE_COLUMNS = {
    "last_name": Member.last_name,
    "first_name": Member.first_name,
    "member_number": Member.member_number,
    "email": Member.email,
    "status": Member.status,
    "category": Member.category,
    "joined_at": Member.joined_at,
    "created_at": Member.created_at,
}


class MemberRepository(
    BaseRepository[Member, MemberCreate, MemberUpdate],
):
    model_class = Member

    async def get_all(  # type: ignore[override]
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: str | None = None,
        category: str | None = None,
        search: str | None = None,
        sort_by: str = "last_name",
        sort_order: str = "asc",
    ) -> list[Member]:
        query = self._base_query()

        if status:
            query = query.where(Member.status == status)
        if category:
            query = query.where(Member.category == category)
        if search:
            term = f"%{search}%"
            query = query.where(
                or_(
                    Member.first_name.ilike(term),
                    Member.last_name.ilike(term),
                    Member.email.ilike(term),
                    Member.member_number.ilike(term),
                )
            )

        # Sorting — allowlist check prevents attribute injection.
        sort_col = SORTABLE_COLUMNS.get(sort_by, Member.last_name)
        if sort_order == "desc":
            query = query.order_by(sort_col.desc())
        else:
            query = query.order_by(sort_col.asc())

        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def status_counts(
        self,
        *,
        search: str | None = None,
    ) -> dict[str, int]:
        """Count members grouped by status, respecting search but not status filter."""
        query = (
            select(Member.status, func.count())
            .select_from(Member)
            .where(Member.tenant_id == self.tenant_id)
            .group_by(Member.status)
        )
        if hasattr(Member, "deleted_at"):
            query = query.where(Member.deleted_at.is_(None))
        if search:
            term = f"%{search}%"
            query = query.where(
                or_(
                    Member.first_name.ilike(term),
                    Member.last_name.ilike(term),
                    Member.email.ilike(term),
                    Member.member_number.ilike(term),
                )
            )
        result = await self.session.execute(query)
        return {row[0]: row[1] for row in result.all()}

    async def count(  # type: ignore[override]
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> int:
        query = select(func.count()).select_from(Member).where(Member.tenant_id == self.tenant_id)
        if hasattr(Member, "deleted_at"):
            query = query.where(Member.deleted_at.is_(None))
        if status:
            query = query.where(Member.status == status)
        if category:
            query = query.where(Member.category == category)
        if search:
            term = f"%{search}%"
            query = query.where(
                or_(
                    Member.first_name.ilike(term),
                    Member.last_name.ilike(term),
                    Member.email.ilike(term),
                    Member.member_number.ilike(term),
                )
            )
        result = await self.session.execute(query)
        return result.scalar_one()
