import uuid
from datetime import date

from sqlalchemy import Select, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord, AttendanceSession
from app.models.catalog import ClubDiscipline
from app.models.division import Division
from app.models.member import Member
from app.models.shooting import (
    ShootingProofCertificate,
    ShootingProofRule,
    ShootingRecordDetail,
)
from app.models.sport import Sport
from app.repositories.base import BaseRepository
from app.schemas.shooting import (
    CertificateIssue,
    CertificateRevoke,
    ShootingProofRuleCreate,
    ShootingProofRuleUpdate,
    ShootingRecordDetailUpdate,
)


class ShootingRuleRepository(
    BaseRepository[ShootingProofRule, ShootingProofRuleCreate, ShootingProofRuleUpdate]
):
    model_class = ShootingProofRule

    async def get_by_key(self, rule_key: str) -> ShootingProofRule | None:
        result = await self.session.execute(
            self._base_query().where(ShootingProofRule.rule_key == rule_key)
        )
        return result.scalar_one_or_none()

    async def get_all_ordered(self) -> list[ShootingProofRule]:
        result = await self.session.execute(
            self._base_query().order_by(ShootingProofRule.rule_key.asc())
        )
        return list(result.scalars().all())


class ShootingDetailRepository(
    BaseRepository[ShootingRecordDetail, ShootingRecordDetailUpdate, ShootingRecordDetailUpdate]
):
    model_class = ShootingRecordDetail

    async def list_for_member(self, member_id: uuid.UUID) -> list[ShootingRecordDetail]:
        """Every detail belonging to one member's own attendance records.

        The read side of the self-service write: `upsert_detail` lets a member
        fill in the discipline and round count of their own external entry, and
        without this they could write it once and never see it again.

        Not filtered to `origin = 'external'`: a member may read what the club
        recorded for them too. Editing stays narrower — that gate lives in the
        service, where the write is.
        """
        result = await self.session.execute(
            self._base_query()
            .join(
                AttendanceRecord,
                ShootingRecordDetail.attendance_record_id == AttendanceRecord.id,
            )
            .where(AttendanceRecord.member_id == member_id)
            .where(AttendanceRecord.deleted_at.is_(None))
            .order_by(AttendanceRecord.occurred_on.desc())
        )
        return list(result.scalars().all())

    async def list_for_session(self, session_id: uuid.UUID) -> list[ShootingRecordDetail]:
        """Every detail belonging to one attendance session.

        One request per session rather than per row: the caller is a list of
        twenty people, and twenty round trips to fill in three fields each would
        be the same answer twenty times over.

        Joined through the record instead of storing the session on the detail —
        the detail describes what somebody shot, and which evening that was is
        already answered next door.
        """
        result = await self.session.execute(
            self._base_query()
            .join(
                AttendanceRecord,
                ShootingRecordDetail.attendance_record_id == AttendanceRecord.id,
            )
            .where(AttendanceRecord.session_id == session_id)
            .where(AttendanceRecord.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def get_by_record(self, attendance_record_id: uuid.UUID) -> ShootingRecordDetail | None:
        result = await self.session.execute(
            self._base_query().where(
                ShootingRecordDetail.attendance_record_id == attendance_record_id
            )
        )
        return result.scalar_one_or_none()


class ShootingCertificateRepository(
    BaseRepository[ShootingProofCertificate, CertificateIssue, CertificateRevoke]
):
    model_class = ShootingProofCertificate

    async def list_with_names(
        self, *, member_id: uuid.UUID | None = None, offset: int = 0, limit: int = 20
    ) -> list[tuple[ShootingProofCertificate, str]]:
        query = (
            self._base_query()
            .add_columns((Member.first_name + " " + Member.last_name).label("member_name"))
            .join(Member, ShootingProofCertificate.member_id == Member.id)
            .order_by(ShootingProofCertificate.issued_at.desc())
        )
        if member_id:
            query = query.where(ShootingProofCertificate.member_id == member_id)
        result = await self.session.execute(query.offset(offset).limit(limit))
        return [(row[0], row[1]) for row in result.all()]

    async def count_filtered(self, *, member_id: uuid.UUID | None = None) -> int:
        query = self._base_query()
        if member_id:
            query = query.where(ShootingProofCertificate.member_id == member_id)
        result = await self.session.execute(select(func.count()).select_from(query.subquery()))
        return result.scalar_one()


class ShootingProofRepository:
    """Read-side of the §14 evaluation, over core attendance data.

    Not a BaseRepository: it owns no table, it asks one question — which of a
    member's attendances count as shooting attendance.
    """

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def _countable(
        self, member_id: uuid.UUID, start: date, end: date
    ) -> Select[tuple[uuid.UUID, date, str, str]]:
        """Live records of the member in the window, shooting sessions only.

        Guests fall out by construction (`member_id` is the join key). Sessions
        of a division that belongs to a sport *without* the shooting module are
        excluded — a Turnverein's shooting section must not count gymnastics
        evenings. Divisionless sessions count: a pure shooting club is not
        required to maintain divisions before its attendance means anything.
        """
        foreign_sport_division = (
            exists()
            .where(Division.id == AttendanceSession.division_id)
            .where(Division.sport_id == Sport.id)
            # Base-ARRAY `.any(value)`: `'shooting' = ANY (modules)`. Mypy only
            # knows the relationship overload of `any`, hence the ignore.
            .where(~Sport.modules.any("shooting"))  # type: ignore[arg-type]
        )
        return (
            select(
                AttendanceRecord.id,
                AttendanceRecord.occurred_on,
                AttendanceRecord.method,
                AttendanceRecord.origin,
            )
            # Outer, because an external self-entry has no session and still
            # counts — its qualification travels in `origin`, not in absence.
            # The foreign-sport exclusion below correlates on the session's
            # division and is simply false for a sessionless row.
            .outerjoin(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
            .where(AttendanceRecord.tenant_id == self.tenant_id)
            .where(AttendanceRecord.member_id == member_id)
            .where(AttendanceRecord.deleted_at.is_(None))
            .where(AttendanceRecord.occurred_on >= start)
            .where(AttendanceRecord.occurred_on <= end)
            .where(~foreign_sport_division)
        )

    async def countable_records(
        self, member_id: uuid.UUID, start: date, end: date
    ) -> list[tuple[uuid.UUID, date, str, str]]:
        """(id, day, method, origin) per countable record.

        Method and origin ride along because a day resting only on the member's
        own word counts the same as any other but must not *read* the same — see
        `ShootingService.evaluate`.
        """
        result = await self.session.execute(self._countable(member_id, start, end))
        return [(row[0], row[1], row[2], row[3]) for row in result.all()]

    async def days_confirming_others(
        self, user_id: uuid.UUID, member_id: uuid.UUID, start: date, end: date
    ) -> set[date]:
        """Days on which this account checked *other* people in.

        The corroboration a supervisor's self-entry can actually offer. Somebody
        who ticked fourteen other people off that evening was demonstrably at the
        range, and those fourteen records were made by other people's presence —
        which is a stronger statement than any tick they could make about
        themselves.

        Not restricted to shooting sessions: what is in question here is whether
        the person was *there*, and running the check-in desk at the club's
        gymnastics evening proves that just as well. Whether the day counts as a
        shooting day is decided separately, by [countable_records].
        """
        result = await self.session.execute(
            select(AttendanceRecord.occurred_on)
            .where(AttendanceRecord.tenant_id == self.tenant_id)
            .where(AttendanceRecord.verified_by_user_id == user_id)
            # `IS DISTINCT FROM`, not `!=`: a guest row has `member_id IS NULL`,
            # and `NULL != <uuid>` is NULL rather than true — so a supervisor whose
            # evening consisted of checking guests in would have come out
            # uncorroborated.
            .where(AttendanceRecord.member_id.is_distinct_from(member_id))
            .where(AttendanceRecord.deleted_at.is_(None))
            .where(AttendanceRecord.occurred_on >= start)
            .where(AttendanceRecord.occurred_on <= end)
            .distinct()
        )
        return {row[0] for row in result.all()}

    async def range_book_rows(self, start: date, end: date) -> list[tuple[object, ...]]:
        """Everything the range book prints, one query, oldest first.

        Outer joins throughout: a manual check-in without shooting detail and a
        guest without member row still belong in the book — the book answers
        who was on the range, not who filled in their discipline.
        """
        supervisor = Member.__table__.alias("supervisor")
        query = (
            select(
                AttendanceRecord.occurred_on,
                AttendanceSession.title,
                AttendanceSession.location,
                func.coalesce(
                    Member.first_name + " " + Member.last_name, AttendanceRecord.guest_name
                ),
                ClubDiscipline.name,
                ShootingRecordDetail.weapon_category,
                ShootingRecordDetail.rounds_fired,
                supervisor.c.first_name + " " + supervisor.c.last_name,
                AttendanceRecord.method,
            )
            .join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id)
            .outerjoin(Member, AttendanceRecord.member_id == Member.id)
            .outerjoin(
                ShootingRecordDetail,
                ShootingRecordDetail.attendance_record_id == AttendanceRecord.id,
            )
            .outerjoin(ClubDiscipline, ShootingRecordDetail.club_discipline_id == ClubDiscipline.id)
            .outerjoin(supervisor, AttendanceSession.supervisor_member_id == supervisor.c.id)
            .where(AttendanceRecord.tenant_id == self.tenant_id)
            .where(AttendanceRecord.deleted_at.is_(None))
            .where(AttendanceRecord.occurred_on >= start)
            .where(AttendanceRecord.occurred_on <= end)
            .order_by(
                AttendanceRecord.occurred_on.asc(),
                AttendanceRecord.checked_in_at.asc(),
            )
        )
        result = await self.session.execute(query)
        return [tuple(row) for row in result.all()]


async def certificate_by_verification_code(
    session: AsyncSession, code: str
) -> tuple[ShootingProofCertificate, str, str] | None:
    """The public verify lookup — deliberately tenant-unscoped.

    The verify page is unauthenticated and has no tenant context; the code
    itself is the credential, globally unique and unguessable. Returns the
    certificate with the club's name and the member's *abbreviated* name —
    whoever finds a lost PDF must not learn more than the page shows.
    """
    from app.models.tenant import Tenant

    result = await session.execute(
        select(ShootingProofCertificate, Tenant.name, Member.first_name, Member.last_name)
        .join(Tenant, ShootingProofCertificate.tenant_id == Tenant.id)
        .join(Member, ShootingProofCertificate.member_id == Member.id)
        .where(ShootingProofCertificate.verification_code == code)
    )
    row = result.first()
    if row is None:
        return None
    certificate, club_name, first_name, last_name = row
    abbreviated = f"{first_name} {last_name[:1]}." if last_name else first_name
    return certificate, club_name, abbreviated
