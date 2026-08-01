import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AdminAuditLog(Base):
    """Append-only record of platform-admin activity.

    Deliberately **not** tenant-scoped: it records actions that cross tenant
    boundaries, and a tenant must not be able to read or alter the log of what
    was done to it. There is no update or delete path — entries are written
    once and only ever read by platform admins.
    """

    __tablename__ = "admin_audit_log"
    __table_args__ = (
        Index("ix_admin_audit_log_actor_created", "actor_user_id", "created_at"),
        Index("ix_admin_audit_log_tenant_created", "tenant_id", "created_at"),
        Index("ix_admin_audit_log_action_created", "action", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    # Who acted. During impersonation this is the impersonated user, and
    # `impersonator_id` names the admin behind it — so the log answers both
    # "whose account did this" and "who was actually at the keyboard".
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    impersonator_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True, index=True
    )

    action: Mapped[str] = mapped_column(String(100), nullable=False)

    # What was acted on. Free-form rather than a FK, because the log outlives
    # the rows it references — a deleted club must not erase its own audit
    # trail.
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    # Tenant the action touched, when applicable. No FK, same reasoning.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
