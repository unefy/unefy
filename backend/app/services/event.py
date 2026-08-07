import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.event import Event, EventRegistration
from app.repositories.competition import CompetitionRepository
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
        self.competitions = CompetitionRepository(session, tenant_id)

    async def _apply_competition_link(self, event: Event) -> None:
        """Validate the competition/session link and force event_type when linked."""
        if event.session_id is not None:
            comp_session = await self.competitions.get_session(event.session_id)
            if comp_session is None:
                raise NotFoundError("Session not found")
            if (
                event.competition_id is not None
                and comp_session.competition_id != event.competition_id
            ):
                raise ValidationError("Session does not belong to the given competition")
            event.competition_id = comp_session.competition_id
            event.event_type = "competition"
        elif event.competition_id is not None:
            if await self.competitions.get_by_id(event.competition_id) is None:
                raise NotFoundError("Competition not found")
            event.event_type = "competition"

    async def create(self, data: EventCreate, created_by: uuid.UUID) -> Event:
        """Create an event, idempotently when the caller names its id.

        Same contract as `MemberService.create`: repeating a request with the
        same `id` returns the event from the first one. What a phone with no
        signal cannot tell is whether its request never arrived or its reply
        never came back, so it has to be safe to just ask again.
        """
        fields = data.model_dump()
        event_id = fields.pop("id", None)

        if event_id is not None:
            existing = await self.events.get_by_id(event_id)
            if existing is not None:
                return existing

        event = Event(
            **fields,
            tenant_id=self.tenant_id,
            created_by=created_by,
            updated_by=created_by,
        )
        if event_id is not None:
            event.id = event_id
        await self._apply_competition_link(event)

        try:
            # See `MemberService.create` for why this is a savepoint, and why
            # the `add` belongs inside it.
            async with self.session.begin_nested():
                self.session.add(event)
                await self.session.flush()
        except IntegrityError:
            if event_id is None:
                raise
            existing = await self.events.get_by_id(event_id)
            if existing is None:
                # Taken by another club's event — see `MemberService.create`.
                raise ConflictError("Event id already in use", code="ID_IN_USE") from None
            return existing

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
        await self._apply_competition_link(event)
        event.updated_by = updated_by
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def competition_name(self, event: Event) -> str | None:
        if event.competition_id is None:
            return None
        comp = await self.competitions.get_by_id(event.competition_id)
        return comp.name if comp else None

    async def register(
        self,
        event_id: uuid.UUID,
        data: EventRegistrationCreate,
        created_by: uuid.UUID,
        enforce_deadline: bool = True,
    ) -> EventRegistration:
        """Register a member. Goes to the waitlist when the event is full.

        ``enforce_deadline=False`` is for the board endpoints: the deadline
        addresses members signing themselves up, and the board adding someone
        after it ("put me down, I forgot") is the normal case, not a bypass.
        A cancelled event refuses everyone either way.
        """
        event = await self.events.get_by_id(event_id)
        if event is None:
            raise NotFoundError("Event not found")
        if event.status == "cancelled":
            raise ConflictError("Event is cancelled")
        if (
            enforce_deadline
            and event.registration_deadline is not None
            and datetime.now(UTC) > event.registration_deadline
        ):
            raise ConflictError("Registration deadline has passed")

        member = await self.members.get_by_id(data.member_id)
        if member is None:
            raise NotFoundError("Member not found")

        existing = await self.registrations.get_any_by_event_and_member(event_id, data.member_id)
        if existing is not None and existing.deleted_at is None:
            raise ConflictError("Member is already registered")

        status = "registered"
        if event.max_participants is not None:
            registered = await self.registrations.count_registered(event_id)
            if registered >= event.max_participants:
                status = "waitlist"

        if existing is not None:
            # A cancelled registration leaves a soft-deleted row, and the
            # unique constraint (tenant, event, member) covers deleted rows
            # too — inserting over it is a 500, not a second registration.
            # Reviving keeps signing up again working and the history linear.
            existing.deleted_at = None
            existing.status = status
            existing.note = data.note
            existing.updated_by = created_by
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

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
