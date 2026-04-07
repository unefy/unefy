import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, SoftDeleteMixin, TenantMixin


class Event(Base, AuditMixin, TenantMixin, SoftDeleteMixin):
    """A competition, training session, or other scheduled event."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_tenant_date", "tenant_id", "date"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Type: "competition", "training", "championship", "other"
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, default="competition")

    # Discipline (optional — can be mixed). Specific results carry their own.
    discipline: Mapped[str | None] = mapped_column(String(100), nullable=True)

    results: Mapped[list["ShootingResult"]] = relationship(
        back_populates="event", lazy="select", cascade="all, delete-orphan"
    )


class ShootingResult(Base, AuditMixin, TenantMixin):
    """One participant's result in an event.

    The `id` is a client-generated UUID so that mobile apps can create
    results offline and sync later — the backend uses upsert semantics
    (idempotent on the same id within the same tenant).
    """

    __tablename__ = "shooting_results"
    __table_args__ = (
        Index("ix_results_tenant_event", "tenant_id", "event_id"),
        Index("ix_results_tenant_member", "tenant_id", "member_id"),
    )

    # Client-generated UUID. The backend falls back to uuid4 if not provided.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("members.id"), nullable=False)

    # Discipline for this specific result (e.g. "air_rifle_10m").
    discipline: Mapped[str] = mapped_column(String(100), nullable=False)

    # Individual shot values (ring numbers), stored as comma-separated ints.
    # Example: "10,9,10,8,10,9,10,10,9,10" for a 10-shot series.
    # JSON array would also work, but CSV is simpler to validate and smaller.
    shots: Mapped[str] = mapped_column(Text, nullable=False)

    # Pre-computed total (sum of shots). Denormalized for fast sorting/filtering.
    total_score: Mapped[int] = mapped_column(Integer, nullable=False)

    # Number of shots (series length).
    shot_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # How the result was recorded.
    # "manual" = typed by hand, "scan" = AI target recognition
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    # Who recorded it (user_id of the person who entered / scanned).
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    # When it was recorded on the device (may differ from created_at if synced later).
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Optional notes or scan metadata (JSON blob or free text).
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    event: Mapped["Event"] = relationship(back_populates="results")
