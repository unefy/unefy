import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, select

from app.models.due import Due, FeeType, MemberFee
from app.models.member import Member
from app.repositories.base import BaseRepository
from app.schemas.due import (
    DueUpdate,
    FeeTypeCreate,
    FeeTypeUpdate,
    MemberFeeCreate,
    MemberFeeUpdate,
)


class FeeTypeRepository(BaseRepository[FeeType, FeeTypeCreate, FeeTypeUpdate]):
    model_class = FeeType

    async def get_by_name(self, name: str) -> FeeType | None:
        query = self._base_query().where(FeeType.name == name)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
    ) -> list[FeeType]:
        query = self._base_query()
        if not include_inactive:
            query = query.where(FeeType.is_active.is_(True))
        query = query.order_by(FeeType.name.asc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())


class MemberFeeRepository(BaseRepository[MemberFee, MemberFeeCreate, MemberFeeUpdate]):
    model_class = MemberFee

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        member_id: uuid.UUID | None = None,
        fee_type_id: uuid.UUID | None = None,
    ) -> list[MemberFee]:
        query = self._base_query()
        if member_id:
            query = query.where(MemberFee.member_id == member_id)
        if fee_type_id:
            query = query.where(MemberFee.fee_type_id == fee_type_id)
        query = query.order_by(MemberFee.valid_from.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_in_period(
        self,
        period_start: date,
        period_end: date,
    ) -> list[tuple[MemberFee, FeeType]]:
        """Assignments overlapping the period, joined with their active fee type.

        Only members that are not soft-deleted are included.
        """
        query = (
            select(MemberFee, FeeType)
            .join(FeeType, MemberFee.fee_type_id == FeeType.id)
            .join(Member, MemberFee.member_id == Member.id)
            .where(MemberFee.tenant_id == self.tenant_id)
            .where(MemberFee.deleted_at.is_(None))
            .where(FeeType.deleted_at.is_(None))
            .where(FeeType.is_active.is_(True))
            .where(Member.deleted_at.is_(None))
            .where(MemberFee.valid_from <= period_end)
            .where((MemberFee.valid_to.is_(None)) | (MemberFee.valid_to >= period_start))
        )
        result = await self.session.execute(query)
        return [(row[0], row[1]) for row in result.all()]


class DueRepository(BaseRepository[Due, DueUpdate, DueUpdate]):
    model_class = Due

    def _filtered_query(
        self,
        *,
        status: str | None = None,
        member_id: uuid.UUID | None = None,
        year: int | None = None,
    ) -> Select[tuple[Due]]:
        query = self._base_query()
        if status:
            query = query.where(Due.status == status)
        if member_id:
            query = query.where(Due.member_id == member_id)
        if year:
            query = query.where(Due.period_start >= date(year, 1, 1))
            query = query.where(Due.period_start <= date(year, 12, 31))
        return query

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: str | None = None,
        member_id: uuid.UUID | None = None,
        year: int | None = None,
    ) -> list[Due]:
        query = (
            self._filtered_query(status=status, member_id=member_id, year=year)
            .order_by(Due.due_date.asc(), Due.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_all_with_member(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: str | None = None,
        member_id: uuid.UUID | None = None,
        year: int | None = None,
    ) -> list[tuple[Due, str, str]]:
        """Dues joined with member first/last name for list display."""
        query = (
            self._filtered_query(status=status, member_id=member_id, year=year)
            .add_columns(Member.first_name, Member.last_name)
            .join(Member, Due.member_id == Member.id)
            .order_by(Due.due_date.asc(), Due.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def count(
        self,
        *,
        status: str | None = None,
        member_id: uuid.UUID | None = None,
        year: int | None = None,
    ) -> int:
        query = self._filtered_query(status=status, member_id=member_id, year=year)
        count_query = select(func.count()).select_from(query.subquery())
        result = await self.session.execute(count_query)
        return result.scalar_one()

    async def get_open_for_sepa(self, *, year: int | None = None) -> list[tuple[Due, Member]]:
        """Open dues of members with complete SEPA data (IBAN + mandate)."""
        query = (
            self._filtered_query(status="open", year=year)
            .add_columns(Member)
            .join(Member, Due.member_id == Member.id)
            .where(Member.deleted_at.is_(None))
            .where(Member.iban.is_not(None))
            .where(Member.sepa_mandate_reference.is_not(None))
            .where(Member.sepa_mandate_date.is_not(None))
            .order_by(Member.last_name.asc(), Due.period_start.asc())
        )
        result = await self.session.execute(query)
        return [(row[0], row[1]) for row in result.all()]

    async def get_existing_period_keys(
        self,
        year: int,
    ) -> set[tuple[uuid.UUID, uuid.UUID, date]]:
        """(member_id, fee_type_id, period_start) of all dues in the given year.

        Includes soft-deleted rows: the DB unique constraint spans them too,
        and a cancelled/deleted due must not be re-assessed silently.
        """
        query = (
            select(Due.member_id, Due.fee_type_id, Due.period_start)
            .where(Due.tenant_id == self.tenant_id)
            .where(Due.period_start >= date(year, 1, 1))
            .where(Due.period_start <= date(year, 12, 31))
        )
        result = await self.session.execute(query)
        return {(row[0], row[1], row[2]) for row in result.all()}

    async def summary(self, *, year: int | None = None) -> dict[str, Decimal | int]:
        query = (
            select(Due.status, func.count(), func.coalesce(func.sum(Due.amount), 0))
            .where(Due.tenant_id == self.tenant_id)
            .where(Due.deleted_at.is_(None))
            .group_by(Due.status)
        )
        if year:
            query = query.where(Due.period_start >= date(year, 1, 1))
            query = query.where(Due.period_start <= date(year, 12, 31))
        result = await self.session.execute(query)
        rows = {row[0]: (row[1], Decimal(row[2])) for row in result.all()}
        open_row = rows.get("open", (0, Decimal("0")))
        paid_row = rows.get("paid", (0, Decimal("0")))
        return {
            "open_count": open_row[0],
            "open_amount": open_row[1],
            "paid_count": paid_row[0],
            "paid_amount": paid_row[1],
        }
