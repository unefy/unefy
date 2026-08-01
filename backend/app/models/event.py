import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, SoftDeleteMixin, TenantModel


class Event(TenantModel, AuditMixin, SoftDeleteMixin):
    """A generic club event: training, meeting, celebration, etc.

    Sport-specific competition series live in the Competition model;
    this is the club-wide calendar entry with optional registration.
    """

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_tenant_starts", "tenant_id", "starts_at"),
        Index("ix_events_tenant_session", "tenant_id", "session_id"),
        Index("ix_events_tenant_competition", "tenant_id", "competition_id"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # "training", "meeting", "celebration", "competition", "other"
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other")

    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Registration
    registration_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    registration_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    max_participants: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # "scheduled" | "cancelled"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")

    # Optional link to the sport layer: a competition and/or one of its sessions.
    competition_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("competitions.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )


class EventRegistration(TenantModel, AuditMixin, SoftDeleteMixin):
    """A member's registration for an event."""

    __tablename__ = "event_registrations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_id", "member_id"),
        Index("ix_event_registrations_tenant_event", "tenant_id", "event_id"),
        Index("ix_event_registrations_tenant_member", "tenant_id", "member_id"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("members.id"), nullable=False)

    # "registered" | "waitlist"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="registered")

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
