import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Invitation(Base, TimestampMixin):
    """A pending offer to join a club.

    Kept in the database rather than Redis (unlike magic links) because it is
    club data: the list of outstanding invitations has to survive a cache flush
    and be visible to everyone who administers the club.

    Only the token's hash is stored — a database dump must not yield working
    invitation links.
    """

    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )

    # Set when the invitation was issued from a member record. On acceptance
    # this is what links `Member.user_id`, so the person's self-service view
    # shows their own dues and registrations instead of an empty profile.
    # Null for people who get access without being members — a treasurer or an
    # external auditor.
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("members.id"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Set when redeemed. A row is kept afterwards so the club can see who joined
    # through which invitation.
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set when an administrator withdraws the invitation before it is used.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # The pending list is read on every visit to the access page and
        # filtered by club, so the composite index matches the real query.
        Index("ix_invitations_tenant_email", "tenant_id", "email"),
    )
