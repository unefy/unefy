import uuid
from datetime import date, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.sql.selectable import ScalarSelect

from app.models.attendance import AttendanceRecord, AttendanceSession
from app.models.member import Member
from app.repositories.base import BaseRepository
from app.schemas.attendance import (
    AttendanceCheckIn,
    AttendanceRecordUpdate,
    AttendanceSessionCreate,
    AttendanceSessionUpdate,
)


class AttendanceSessionRepository(
    BaseRepository[AttendanceSession, AttendanceSessionCreate, AttendanceSessionUpdate]
):
    model_class = AttendanceSession

    def _filtered_query(
        self,
        *,
        opens_after: datetime | None = None,
        opens_before: datetime | None = None,
        division_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> Select[tuple[AttendanceSession]]:
        query = self._base_query()
        if opens_after:
            query = query.where(AttendanceSession.opens_at >= opens_after)
        if opens_before:
            query = query.where(AttendanceSession.opens_at < opens_before)
        if division_id:
            query = query.where(AttendanceSession.division_id == division_id)
        if status:
            query = query.where(AttendanceSession.status == status)
        return query

    def _record_count_subquery(self) -> ScalarSelect[int]:
        """Live record count per session — correlated, so listing stays one query."""
        return (
            select(func.count())
            .select_from(AttendanceRecord)
            .where(AttendanceRecord.session_id == AttendanceSession.id)
            .where(AttendanceRecord.tenant_id == self.tenant_id)
            .where(AttendanceRecord.deleted_at.is_(None))
            .correlate(AttendanceSession)
            .scalar_subquery()
        )

    async def list_with_counts(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        opens_after: datetime | None = None,
        opens_before: datetime | None = None,
        division_id: uuid.UUID | None = None,
        status: str | None = None,
        sort_order: str = "desc",
    ) -> list[tuple[AttendanceSession, int, str | None]]:
        """Sessions with their live record count and the supervisor's name."""
        supervisor = Member.__table__.alias("supervisor")
        query = self._filtered_query(
            opens_after=opens_after,
            opens_before=opens_before,
            division_id=division_id,
            status=status,
        ).add_columns(
            self._record_count_subquery().label("record_count"),
            (supervisor.c.first_name + " " + supervisor.c.last_name).label("supervisor_name"),
        )
        query = query.outerjoin(
            supervisor, AttendanceSession.supervisor_member_id == supervisor.c.id
        )
        if sort_order == "asc":
            query = query.order_by(AttendanceSession.opens_at.asc())
        else:
            query = query.order_by(AttendanceSession.opens_at.desc())
        result = await self.session.execute(query.offset(offset).limit(limit))
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def count(
        self,
        *,
        opens_after: datetime | None = None,
        opens_before: datetime | None = None,
        division_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> int:
        query = self._filtered_query(
            opens_after=opens_after,
            opens_before=opens_before,
            division_id=division_id,
            status=status,
        )
        result = await self.session.execute(select(func.count()).select_from(query.subquery()))
        return result.scalar_one()

    async def exists_any_state(self, session_id: uuid.UUID) -> bool:
        """Tenant-scoped existence check that also sees deleted sessions.

        The audit trail must stay readable after the session leaves the live
        view — that is the moment it matters most.
        """
        result = await self.session.execute(
            select(AttendanceSession.id)
            .where(AttendanceSession.tenant_id == self.tenant_id)
            .where(AttendanceSession.id == session_id)
        )
        return result.first() is not None

    async def supervisor_name(self, session_row: AttendanceSession) -> str | None:
        if session_row.supervisor_member_id is None:
            return None
        result = await self.session.execute(
            select(Member.first_name, Member.last_name)
            .where(Member.tenant_id == self.tenant_id)
            .where(Member.id == session_row.supervisor_member_id)
        )
        row = result.first()
        return f"{row[0]} {row[1]}" if row else None

    async def record_count(self, session_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(AttendanceRecord)
            .where(AttendanceRecord.tenant_id == self.tenant_id)
            .where(AttendanceRecord.session_id == session_id)
            .where(AttendanceRecord.deleted_at.is_(None))
        )
        return result.scalar_one()


class AttendanceRecordRepository(
    BaseRepository[AttendanceRecord, AttendanceCheckIn, AttendanceRecordUpdate]
):
    model_class = AttendanceRecord

    async def get_for_session(
        self, session_id: uuid.UUID
    ) -> list[tuple[AttendanceRecord, str, str, str]]:
        """Records of one session with member first/last name and number."""
        query = (
            self._base_query()
            .where(AttendanceRecord.session_id == session_id)
            .add_columns(Member.first_name, Member.last_name, Member.member_number)
            .join(Member, AttendanceRecord.member_id == Member.id)
            .order_by(Member.last_name.asc(), Member.first_name.asc())
        )
        result = await self.session.execute(query)
        return [(row[0], row[1], row[2], row[3]) for row in result.all()]

    async def get_active(
        self, session_id: uuid.UUID, member_id: uuid.UUID
    ) -> AttendanceRecord | None:
        """The member's live record for this session, ignoring corrected ones."""
        query = (
            self._base_query()
            .where(AttendanceRecord.session_id == session_id)
            .where(AttendanceRecord.member_id == member_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def all_ids_for_session(self, session_id: uuid.UUID) -> list[uuid.UUID]:
        """Every record id of a session, deleted ones included.

        The trail of a session has to cover records that were corrected away —
        those are the entries someone actually goes looking for.
        """
        result = await self.session.execute(
            select(AttendanceRecord.id)
            .where(AttendanceRecord.tenant_id == self.tenant_id)
            .where(AttendanceRecord.session_id == session_id)
        )
        return [row[0] for row in result.all()]

    async def exists_any_state(self, record_id: uuid.UUID) -> bool:
        """Tenant-scoped existence check that also sees corrected-away records.

        A soft-deleted record drops out of every ordinary query, but its trail
        has to remain readable — otherwise deleting a record would erase the
        evidence that it was deleted.
        """
        result = await self.session.execute(
            select(AttendanceRecord.id)
            .where(AttendanceRecord.tenant_id == self.tenant_id)
            .where(AttendanceRecord.id == record_id)
        )
        return result.first() is not None

    def _member_query(
        self,
        member_id: uuid.UUID,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> Select[tuple[AttendanceRecord]]:
        query = self._base_query().where(AttendanceRecord.member_id == member_id)
        if from_date:
            query = query.where(AttendanceRecord.occurred_on >= from_date)
        if to_date:
            query = query.where(AttendanceRecord.occurred_on <= to_date)
        return query

    async def get_for_member(
        self,
        member_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 20,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[tuple[AttendanceRecord, str, str | None]]:
        """A member's own attendance history, with the session as context."""
        query = (
            self._member_query(member_id, from_date=from_date, to_date=to_date)
            .add_columns(AttendanceSession.title, AttendanceSession.location)
            .join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
            .order_by(AttendanceRecord.occurred_on.desc(), AttendanceRecord.checked_in_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def count_for_member(
        self,
        member_id: uuid.UUID,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> int:
        query = self._member_query(member_id, from_date=from_date, to_date=to_date)
        result = await self.session.execute(select(func.count()).select_from(query.subquery()))
        return result.scalar_one()
