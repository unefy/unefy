import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """User account. Owned by the backend — single source of truth for all clients."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    image: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Preferences
    locale: Mapped[str | None] = mapped_column(String(5), nullable=True)  # e.g. "de", "en"

    # OAuth provider links
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    # Passkey credentials stored separately (future)

    tenant_memberships: Mapped[list["TenantMembership"]] = relationship(
        back_populates="user", lazy="select"
    )


class TenantMembership(Base, TimestampMixin):
    """Links users to tenants with a role. A user can be member of multiple tenants (SaaS)."""

    __tablename__ = "tenant_memberships"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="member"
    )  # owner, admin, board, member
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="tenant_memberships")
