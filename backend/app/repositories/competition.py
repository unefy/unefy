import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.competition import Competition, Entry, Session
from app.repositories.base import BaseRepository
from app.schemas.competition import (
    CompetitionCreate,
    CompetitionUpdate,
    EntryCreate,
    EntryUpdate,
    SessionCreate,
    SessionUpdate,
)


class CompetitionRepository(
    BaseRepository[Competition, CompetitionCreate, CompetitionUpdate],  # type: ignore[type-var]
):
    """Competition repository with idempotent create for offline sync."""

    model_class = Competition

    def _base_query(self) -> Any:
        return (
            select(Competition)
            .where(Competition.tenant_id == self.tenant_id)
            .where(Competition.deleted_at.is_(None))
        )

    async def create(self, data: CompetitionCreate) -> Competition:
        comp_id = data.id or uuid.uuid4()
        existing = await self.get_by_id(comp_id)
        if existing:
            return existing
        entity = Competition(
            id=comp_id,
            tenant_id=self.tenant_id,
            **data.model_dump(exclude={"id"}),
        )
        self.session.add(entity)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.get_by_id(comp_id)
            if existing:
                return existing
            raise
        await self.session.refresh(entity)
        return entity

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        competition_type: str | None = None,
        sort_order: str = "desc",
    ) -> list[Competition]:
        query = self._base_query()
        if competition_type:
            query = query.where(Competition.competition_type == competition_type)
        order = (
            Competition.start_date.desc() if sort_order == "desc" else Competition.start_date.asc()
        )
        query = query.order_by(order).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(self, competition_type: str | None = None) -> int:
        query = (
            select(func.count())
            .select_from(Competition)
            .where(Competition.tenant_id == self.tenant_id)
            .where(Competition.deleted_at.is_(None))
        )
        if competition_type:
            query = query.where(Competition.competition_type == competition_type)
        result = await self.session.execute(query)
        return result.scalar_one()


class SessionRepository:
    def __init__(
        self, session: AsyncSession, tenant_id: uuid.UUID, competition_id: uuid.UUID
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.competition_id = competition_id

    def _base_query(self) -> Any:
        return (
            select(Session)
            .where(Session.tenant_id == self.tenant_id)
            .where(Session.competition_id == self.competition_id)
            .where(Session.deleted_at.is_(None))
        )

    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        query = self._base_query().where(Session.id == session_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(self, *, offset: int = 0, limit: int = 100) -> list[Session]:
        query = self._base_query().order_by(Session.date.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(self) -> int:
        query = (
            select(func.count())
            .select_from(Session)
            .where(Session.tenant_id == self.tenant_id)
            .where(Session.competition_id == self.competition_id)
            .where(Session.deleted_at.is_(None))
        )
        result = await self.session.execute(query)
        return result.scalar_one()

    async def create(self, data: SessionCreate) -> Session:
        sess_id = data.id or uuid.uuid4()
        existing = await self.get_by_id(sess_id)
        if existing:
            return existing
        entity = Session(
            id=sess_id,
            tenant_id=self.tenant_id,
            competition_id=self.competition_id,
            **data.model_dump(exclude={"id"}),
        )
        self.session.add(entity)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.get_by_id(sess_id)
            if existing:
                return existing
            raise
        await self.session.refresh(entity)
        return entity

    async def update(self, session_id: uuid.UUID, data: SessionUpdate) -> Session | None:
        entity = await self.get_by_id(session_id)
        if entity is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(entity, field, value)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def soft_delete(self, session_id: uuid.UUID) -> bool:
        entity = await self.get_by_id(session_id)
        if entity is None:
            return False
        from datetime import UTC, datetime

        entity.deleted_at = datetime.now(UTC)
        await self.session.flush()
        return True


class EntryRepository:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID, session_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.session_id = session_id

    def _base_query(self) -> Any:
        return (
            select(Entry)
            .where(Entry.tenant_id == self.tenant_id)
            .where(Entry.session_id == self.session_id)
            .where(Entry.deleted_at.is_(None))
        )

    async def get_by_id(self, entry_id: uuid.UUID) -> Entry | None:
        query = self._base_query().where(Entry.id == entry_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 500,
        member_id: uuid.UUID | None = None,
    ) -> list[Entry]:
        query = self._base_query()
        if member_id:
            query = query.where(Entry.member_id == member_id)
        query = query.order_by(Entry.recorded_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(self, member_id: uuid.UUID | None = None) -> int:
        query = (
            select(func.count())
            .select_from(Entry)
            .where(Entry.tenant_id == self.tenant_id)
            .where(Entry.session_id == self.session_id)
            .where(Entry.deleted_at.is_(None))
        )
        if member_id:
            query = query.where(Entry.member_id == member_id)
        result = await self.session.execute(query)
        return result.scalar_one()

    async def create_idempotent(
        self, data: EntryCreate, *, recorded_by: uuid.UUID | None = None
    ) -> tuple[Entry, bool]:
        entry_id = data.id or uuid.uuid4()
        existing = await self.get_by_id(entry_id)
        if existing:
            return existing, False

        entity = Entry(
            id=entry_id,
            session_id=self.session_id,
            tenant_id=self.tenant_id,
            member_id=data.member_id,
            score_value=data.score_value,
            score_unit=data.score_unit,
            discipline=data.discipline,
            details=data.details,
            source=data.source,
            recorded_by=recorded_by,
            recorded_at=data.recorded_at,
            notes=data.notes,
        )
        self.session.add(entity)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.get_by_id(entry_id)
            if existing:
                return existing, False
            raise
        await self.session.refresh(entity)
        return entity, True

    async def update(self, entry_id: uuid.UUID, data: EntryUpdate) -> Entry | None:
        entity = await self.get_by_id(entry_id)
        if entity is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(entity, field, value)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def soft_delete(self, entry_id: uuid.UUID) -> bool:
        entity = await self.get_by_id(entry_id)
        if entity is None:
            return False
        from datetime import UTC, datetime

        entity.deleted_at = datetime.now(UTC)
        await self.session.flush()
        return True


class ScoreboardRepository:
    """Aggregates entries across all sessions of a competition."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def scoreboard(
        self,
        competition_id: uuid.UUID,
        discipline: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            select(
                Entry.member_id,
                func.sum(Entry.score_value).label("total_score"),
                func.count(Entry.id).label("entry_count"),
                func.avg(Entry.score_value).label("average_score"),
                func.max(Entry.score_value).label("best_score"),
            )
            .join(Session, Session.id == Entry.session_id)
            .where(Session.competition_id == competition_id)
            .where(Entry.tenant_id == self.tenant_id)
            .where(Session.deleted_at.is_(None))
            .where(Entry.deleted_at.is_(None))
        )
        if discipline:
            query = query.where(
                (Entry.discipline == discipline) | (Session.discipline == discipline)
            )
        query = query.group_by(Entry.member_id)

        result = await self.session.execute(query)
        rows = result.all()
        return [
            {
                "member_id": str(row.member_id),
                "total_score": float(row.total_score),
                "entry_count": row.entry_count,
                "average_score": round(float(row.average_score), 2),
                "best_score": float(row.best_score),
            }
            for row in rows
        ]
