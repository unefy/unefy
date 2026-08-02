import uuid

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

    async def get_all(
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

    async def directory(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
    ) -> list[Member]:
        """Active members for the member-facing directory.

        Deliberately not `get_all` with a filter: that one also matches on email
        and member number, which would let any member confirm whether a given
        address belongs to the club. This searches names only, and returns only
        active members — a directory of former members answers no question a
        member has.
        """
        query = self._base_query().where(Member.status == "active")
        if search:
            term = f"%{search}%"
            query = query.where(or_(Member.first_name.ilike(term), Member.last_name.ilike(term)))
        query = (
            query.order_by(Member.last_name.asc(), Member.first_name.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def directory_count(self, *, search: str | None = None) -> int:
        query = (
            select(func.count())
            .select_from(Member)
            .where(
                Member.tenant_id == self.tenant_id,
                Member.deleted_at.is_(None),
                Member.status == "active",
            )
        )
        if search:
            term = f"%{search}%"
            query = query.where(or_(Member.first_name.ilike(term), Member.last_name.ilike(term)))
        result = await self.session.execute(query)
        return int(result.scalar_one())

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

    async def count(
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

    async def get_by_user_id(self, user_id: uuid.UUID) -> Member | None:
        """The member record belonging to a login account, if one is linked.

        Not every user is a member (an admin may only administer), and not every
        member has a login. Self-service endpoints need the link to exist.
        """
        query = self._base_query().where(Member.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalars().first()
