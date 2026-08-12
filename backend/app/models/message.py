"""A round mail and the people it was sent to.

Two tables, because sending is not atomic: at 200 addresses, 197 leave and
three bounce. A single row with a status could only say "sent" and would hide
exactly the part somebody has to act on.

The recipients are written when the message is queued and never recomputed.
A list resolved again next week answers a different question — "who is in the
club today" instead of "who received the invitation".
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, TenantModel, TimestampMixin

#: A duty communication or a mailing. See app/schemas/message.py — the whole
#: consent rule hangs off this one column.
MESSAGE_KINDS = ("notice", "newsletter")

#: `queued` the moment the recipients are frozen; `sending` while the loop
#: works through them; `sent` when none are left pending. `failed` is for a
#: message where every single recipient failed — anything less is partial and
#: readable in the rows.
MESSAGE_STATUSES = ("queued", "sending", "sent", "failed")

#: `skipped` is not `failed`: it is a decision (no address, no consent, or an
#: installation that holds mail back), not a mail server saying no.
RECIPIENT_STATUSES = ("pending", "sent", "failed", "skipped")


class EmailMessage(TenantModel, AuditMixin):
    """One round mail, as it was sent."""

    __tablename__ = "email_messages"
    __table_args__ = (
        CheckConstraint("kind IN ('notice', 'newsletter')", name="ck_email_messages_kind"),
        CheckConstraint(
            "status IN ('queued', 'sending', 'sent', 'failed')",
            name="ck_email_messages_status",
        ),
        # The sending loop's query: whatever is not finished, oldest first.
        Index("ix_email_messages_status", "status", "queued_at"),
        Index("ix_email_messages_tenant_queued", "tenant_id", "queued_at"),
    )

    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    #: The *selection*, not its result — "everyone", "the treasurers", "who
    #: owes for 2026". Kept so the list can be explained later, and so the
    #: next message can start from the same choice.
    audience: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")

    sent_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: Frozen at queueing time. Counting the rows would give the same number
    #: today and a different one after a member is deleted.
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class EmailRecipient(TenantModel, TimestampMixin):
    """One address on one message, and what became of it."""

    __tablename__ = "email_recipients"
    __table_args__ = (
        # No address is *delivered to* twice — a couple sharing a mailbox gets
        # one invitation, not two. Partial, because the second of them still
        # gets a row: `skipped` with reason `duplicate`, so the record answers
        # "did Erika get it" with "yes, at the address she shares with Hans"
        # instead of leaving her out of the list entirely.
        Index(
            "uq_email_recipients_delivered_email",
            "message_id",
            "email",
            unique=True,
            postgresql_where=text("status <> 'skipped'"),
        ),
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'skipped')",
            name="ck_email_recipients_status",
        ),
        # The loop's query: the next few pending rows of a message.
        Index("ix_email_recipients_message_status", "message_id", "status"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False
    )
    #: SET NULL rather than CASCADE: deleting a member must not rewrite the
    #: record of what the club sent out last spring.
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )

    #: The address as it was at sending time. A member who changes it later
    #: did not receive the mail at the new one.
    email: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    #: Why it was skipped: no_email, refused, not_asked, duplicate, held_back.
    reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    #: What the mail server said, shortened. Only for `failed`.
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    #: How often delivery was attempted, so a permanent failure stops at
    #: `EMAIL_MAX_ATTEMPTS` instead of being retried until the end of time.
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
