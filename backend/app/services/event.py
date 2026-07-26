import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.event import Event, EventRegistration
from app.repositories.event import EventRegistrationRepository, EventRepository
from app.repositories.member import MemberRepository
from app.schemas.event import EventCreate, EventRegistrationCreate, EventUpdate


class EventService:
    """Business logic for events and registrations."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.events = EventRepository(session, tenant_id)
        self.registrations = EventRegistrationRepository(session, tenant_id)
        self.members = MemberRepository(session, tenant_id)

    async def create(self, data: EventCreate, created_by: uuid.UUID) -> Event:
        event = Event(
            **data.model_dump(),
            tenant_id=self.tenant_id,
            created_by=created_by,
            updated_by=created_by,
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def update(
        self, event_id: uuid.UUID, data: EventUpdate, updated_by: uuid.UUID
    ) -> Event | None:
        event = await self.events.get_by_id(event_id)
        if event is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(event, field, value)
        if event.ends_at is not None and event.ends_at < event.starts_at:
            raise ValidationError("ends_at must not be before starts_at")
        event.updated_by = updated_by
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def register(
        self,
        event_id: uuid.UUID,
        data: EventRegistrationCreate,
        created_by: uuid.UUID,
    ) -> EventRegistration:
        """Register a member. Goes to the waitlist when the event is full."""
        event = await self.events.get_by_id(event_id)
        if event is None:
            raise NotFoundError("Event not found")
        if event.status == "cancelled":
            raise ConflictError("Event is cancelled")
        if (
            event.registration_deadline is not None
            and datetime.now(UTC) > event.registration_deadline
        ):
            raise ConflictError("Registration deadline has passed")

        member = await self.members.get_by_id(data.member_id)
        if member is None:
            raise NotFoundError("Member not found")

        existing = await self.registrations.get_by_event_and_member(event_id, data.member_id)
        if existing is not None:
            raise ConflictError("Member is already registered")

        status = "registered"
        if event.max_participants is not None:
            registered = await self.registrations.count_registered(event_id)
            if registered >= event.max_participants:
                status = "waitlist"

        registration = EventRegistration(
            tenant_id=self.tenant_id,
            event_id=event_id,
            member_id=data.member_id,
            status=status,
            note=data.note,
            created_by=created_by,
            updated_by=created_by,
        )
        self.session.add(registration)
        await self.session.flush()
        await self.session.refresh(registration)
        return registration

    async def unregister(self, event_id: uuid.UUID, registration_id: uuid.UUID) -> bool:
        """Remove a registration and promote the first waitlisted member."""
        registration = await self.registrations.get_by_id(registration_id)
        if registration is None or registration.event_id != event_id:
            return False
        was_registered = registration.status == "registered"
        deleted = await self.registrations.soft_delete(registration_id)
        if deleted and was_registered:
            await self._promote_from_waitlist(event_id)
        return deleted

    async def _promote_from_waitlist(self, event_id: uuid.UUID) -> None:
        rows = await self.registrations.get_for_event(event_id)
        for registration, _first, _last in rows:
            if registration.status == "waitlist":
                registration.status = "registered"
                await self.session.flush()
                return
