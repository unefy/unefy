import uuid
from datetime import date

from sqlalchemy import Select, and_, func, or_, select

from app.models.division import Division
from app.models.function import Function, MemberFunction
from app.models.member import Member
from app.repositories.base import BaseRepository
from app.schemas.function import (
    FunctionCreate,
    FunctionUpdate,
    MemberFunctionCreate,
    MemberFunctionUpdate,
)


class FunctionRepository(BaseRepository[Function, FunctionCreate, FunctionUpdate]):
    model_class = Function

    async def get_by_name(self, name: str) -> Function | None:
        query = self._base_query().where(Function.name == name)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 200,
        include_inactive: bool = False,
    ) -> list[Function]:
        query = self._base_query()
        if not include_inactive:
            query = query.where(Function.is_active.is_(True))
        query = (
            query.order_by(Function.sort_order.asc(), Function.name.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())


class MemberFunctionRepository(
    BaseRepository[MemberFunction, MemberFunctionCreate, MemberFunctionUpdate]
):
    model_class = MemberFunction

    def _with_names(self) -> Select[tuple[MemberFunction, Function, Division]]:
        # The Division join is an outer join — rows can carry None there even
        # though SQLAlchemy's typing cannot express it in the Select type.
        return (
            select(MemberFunction, Function, Division)
            .join(Function, MemberFunction.function_id == Function.id)
            .join(Division, MemberFunction.division_id == Division.id, isouter=True)
            .where(MemberFunction.tenant_id == self.tenant_id)
        )

    async def list_for_member(
        self, member_id: uuid.UUID
    ) -> list[tuple[MemberFunction, Function, Division | None]]:
        """All terms of a member, newest first. Unpaginated on purpose — a
        member holds a handful of offices over a lifetime, not pages of them."""
        query = (
            self._with_names()
            .where(MemberFunction.member_id == member_id)
            .order_by(MemberFunction.valid_from.desc(), Function.sort_order.asc())
        )
        result = await self.session.execute(query)
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def holders(
        self, at: date
    ) -> list[tuple[MemberFunction, Function, Division | None, Member]]:
        """Who holds which office at the given date."""
        query = (
            self._with_names()
            .add_columns(Member)
            .join(Member, MemberFunction.member_id == Member.id)
            .where(Member.deleted_at.is_(None))
            .where(MemberFunction.valid_from <= at)
            .where(or_(MemberFunction.valid_to.is_(None), MemberFunction.valid_to >= at))
            .order_by(Function.sort_order.asc(), Function.name.asc(), Member.last_name.asc())
        )
        result = await self.session.execute(query)
        return [(row[0], row[1], row[2], row[3]) for row in result.all()]

    async def overlap_exists(
        self,
        *,
        member_id: uuid.UUID,
        function_id: uuid.UUID,
        division_id: uuid.UUID | None,
        valid_from: date,
        valid_to: date | None,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """True if the member already holds this function (same division) in an
        overlapping period. Open-ended terms overlap everything after their start."""
        division_match = (
            MemberFunction.division_id.is_(None)
            if division_id is None
            else MemberFunction.division_id == division_id
        )
        conditions = [
            MemberFunction.tenant_id == self.tenant_id,
            MemberFunction.member_id == member_id,
            MemberFunction.function_id == function_id,
            division_match,
            # existing.end >= new.start (open end = infinity)
            or_(MemberFunction.valid_to.is_(None), MemberFunction.valid_to >= valid_from),
        ]
        if valid_to is not None:
            # existing.start <= new.end
            conditions.append(MemberFunction.valid_from <= valid_to)
        if exclude_id is not None:
            conditions.append(MemberFunction.id != exclude_id)

        query = select(func.count()).select_from(MemberFunction).where(and_(*conditions))
        result = await self.session.execute(query)
        return result.scalar_one() > 0

    async def count_for_function(self, function_id: uuid.UUID) -> int:
        """Number of terms (including historic ones) pointing at a function."""
        query = (
            select(func.count())
            .select_from(MemberFunction)
            .where(MemberFunction.tenant_id == self.tenant_id)
            .where(MemberFunction.function_id == function_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one()
