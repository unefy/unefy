import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditMixin, Base, SoftDeleteMixin, TenantMixin


class Competition(Base, AuditMixin, TenantMixin, SoftDeleteMixin):
    """Top-level container: a league, competition, or training series.

    Sport-agnostic. Holds scoring configuration and time span.
    """

    __tablename__ = "competitions"
    __table_args__ = (Index("ix_competitions_tenant_type", "tenant_id", "competition_type"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # "league", "competition", "training"
    competition_type: Mapped[str] = mapped_column(String(50), nullable=False, default="competition")

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Scoring: higher is better (shooting, archery) vs lower (running, swimming).
    scoring_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="highest_wins")
    # Unit label for display ("Ringe", "Punkte", "Sekunden", "Meter").
    scoring_unit: Mapped[str] = mapped_column(String(50), nullable=False, default="Punkte")

    # Available disciplines for this competition (JSON array of strings).
    # e.g. ["Luftgewehr 10m", "Sportpistole 25m"]
    disciplines: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="competition",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="Session.date",
    )


class Session(Base, AuditMixin, TenantMixin, SoftDeleteMixin):
    """One round, date, or discipline-block within a competition."""

    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_tenant_competition", "tenant_id", "competition_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    competition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Discipline for this session (overrides or narrows the competition's list).
    discipline: Mapped[str | None] = mapped_column(String(100), nullable=True)

    competition: Mapped["Competition"] = relationship(back_populates="sessions")
    entries: Mapped[list["Entry"]] = relationship(
        back_populates="session",
        lazy="select",
        cascade="all, delete-orphan",
        order_by="Entry.score_value.desc()",
    )


class Entry(Base, AuditMixin, TenantMixin, SoftDeleteMixin):
    """One participant's result in a session.

    Sport-agnostic core: `score_value` is the single ranking number.
    Sport-specific data lives in `details` (free-form JSONB).

    The `id` is a client-generated UUID for idempotent offline sync.
    """

    __tablename__ = "entries"
    __table_args__ = (
        Index("ix_entries_tenant_session", "tenant_id", "session_id"),
        Index("ix_entries_tenant_member", "tenant_id", "member_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("members.id"), nullable=False)

    # The one number that determines ranking.
    score_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Display unit (inherited from competition or overridden).
    score_unit: Mapped[str] = mapped_column(String(50), nullable=False, default="Punkte")

    discipline: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Free-form sport-specific data (JSONB).
    # Shooting: {"shots": [...], "target_type": "air_rifle_10m"}
    # Running: {"splits": [...], "distance_m": 5000}
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # "manual" | "scan"
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    # Who recorded it (user_id).
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    # When recorded on the device (may differ from created_at if synced later).
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped["Session"] = relationship(back_populates="entries")
