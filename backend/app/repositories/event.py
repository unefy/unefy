import uuid
from datetime import datetime

from sqlalchemy import Select, func, select

from app.models.competition import Competition
from app.models.event import Event, EventRegistration
from app.models.member import Member
from app.repositories.base import BaseRepository
from app.schemas.event import EventCreate, EventRegistrationCreate, EventUpdate


class EventRepository(BaseRepository[Event, EventCreate, EventUpdate]):
    model_class = Event

    def _filtered_query(
        self,
        *,
        event_type: str | None = None,
        starts_after: datetime | None = None,
        starts_before: datetime | None = None,
        competition_id: uuid.UUID | None = None,
    ) -> Select[tuple[Event]]:
        query = self._base_query()
        if event_type:
            query = query.where(Event.event_type == event_type)
        if starts_after:
            query = query.where(Event.starts_at >= starts_after)
        if starts_before:
            query = query.where(Event.starts_at < starts_before)
        if competition_id:
            query = query.where(Event.competition_id == competition_id)
        return query

    async def get_all(  # type: ignore[override]
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        event_type: str | None = None,
        starts_after: datetime | None = None,
        starts_before: datetime | None = None,
        competition_id: uuid.UUID | None = None,
        sort_order: str = "asc",
    ) -> list[tuple[Event, int, str | None]]:
        """Events with their active registration count and competition name."""
        reg_count = (
            select(func.count())
            .select_from(EventRegistration)
            .where(EventRegistration.event_id == Event.id)
            .where(EventRegistration.tenant_id == self.tenant_id)
            .where(EventRegistration.deleted_at.is_(None))
            .where(EventRegistration.status == "registered")
            .correlate(Event)
            .scalar_subquery()
        )
        query = self._filtered_query(
            event_type=event_type,
            starts_after=starts_after,
            starts_before=starts_before,
            competition_id=competition_id,
        ).add_columns(
            reg_count.label("registered_count"),
            Competition.name.label("competition_name"),
        )
        query = query.outerjoin(Competition, Event.competition_id == Competition.id)
        if sort_order == "desc":
            query = query.order_by(Event.starts_at.desc())
        else:
            query = query.order_by(Event.starts_at.asc())
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def count(  # type: ignore[override]
        self,
        *,
        event_type: str | None = None,
        starts_after: datetime | None = None,
        starts_before: datetime | None = None,
        competition_id: uuid.UUID | None = None,
    ) -> int:
        query = self._filtered_query(
            event_type=event_type,
            starts_after=starts_after,
            starts_before=starts_before,
            competition_id=competition_id,
        )
        count_query = select(func.count()).select_from(query.subquery())
        result = await self.session.execute(count_query)
        return result.scalar_one()

    async def get_by_session(self, session_id: uuid.UUID) -> Event | None:
        query = self._base_query().where(Event.session_id == session_id)
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_event_ids_by_sessions(
        self, session_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, uuid.UUID]:
        """Map session_id -> event_id for all events linked to the given sessions."""
        if not session_ids:
            return {}
        query = (
            select(Event.session_id, Event.id)
            .where(Event.tenant_id == self.tenant_id)
            .where(Event.deleted_at.is_(None))
            .where(Event.session_id.in_(session_ids))
        )
        result = await self.session.execute(query)
        return {row[0]: row[1] for row in result.all()}


class EventRegistrationRepository(
    BaseRepository[EventRegistration, EventRegistrationCreate, EventRegistrationCreate],
):
    model_class = EventRegistration

    async def get_for_event(self, event_id: uuid.UUID) -> list[tuple[EventRegistration, str, str]]:
        """Registrations of an event with member first/last name."""
        query = (
            self._base_query()
            .where(EventRegistration.event_id == event_id)
            .add_columns(Member.first_name, Member.last_name)
            .join(Member, EventRegistration.member_id == Member.id)
            .order_by(EventRegistration.created_at.asc())
        )
        result = await self.session.execute(query)
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def get_by_event_and_member(
        self, event_id: uuid.UUID, member_id: uuid.UUID
    ) -> EventRegistration | None:
        query = (
            self._base_query()
            .where(EventRegistration.event_id == event_id)
            .where(EventRegistration.member_id == member_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def count_registered(self, event_id: uuid.UUID) -> int:
        query = (
            select(func.count())
            .select_from(EventRegistration)
            .where(EventRegistration.tenant_id == self.tenant_id)
            .where(EventRegistration.event_id == event_id)
            .where(EventRegistration.deleted_at.is_(None))
            .where(EventRegistration.status == "registered")
        )
        result = await self.session.execute(query)
        return result.scalar_one()
