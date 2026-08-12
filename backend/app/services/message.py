"""Composing a round mail, and freezing who it goes to.

The sending itself is not here — that is `app/tasks/mail_queue.py`, which
works through the rows this service writes. The split is the point: queueing
must be fast and must not depend on a mail server being reachable, and a board
member pressing "send" must not wait for two hundred SMTP conversations.
"""

import uuid

# `replace` and not `**recipient.__dict__`: the dataclass has slots, so it has
# no __dict__ at all and that spelling raises at runtime rather than in mypy.
from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import AppError, NotFoundError, ValidationError
from app.dependencies import AuthContext
from app.integrations.email import may_send, send_email
from app.models.message import EmailMessage, EmailRecipient
from app.schemas.message import Audience, AudienceSummary, MessageKind
from app.services.audit import record_tenant_action
from app.services.recipients import (
    RecipientResolver,
    ResolvedRecipient,
    SkipReason,
    summarize,
)

MESSAGE_TARGET = "email_message"

#: Skipped because somebody else on this message already has the address —
#: a couple sharing a mailbox gets one invitation.
DUPLICATE: SkipReason = "duplicate"
#: Skipped because this installation is not sending member mail at all.
HELD_BACK: SkipReason = "held_back"


class MessageService:
    def __init__(self, session: AsyncSession, auth: AuthContext) -> None:
        self.session = session
        self.auth = auth
        self.tenant_id = auth.tenant
        self.resolver = RecipientResolver(session, self.tenant_id)

    # --- Before anything is sent ---

    async def preview(
        self, audience: Audience, kind: MessageKind, *, settings: Settings
    ) -> tuple[AudienceSummary, list[ResolvedRecipient]]:
        """Who this would reach, counted, without writing anything.

        The same code path that queueing uses, so the number on the screen is
        the number that will be sent — a preview computed differently is a
        preview of something else.
        """
        planned = await self._plan(audience, kind, settings=settings)
        return summarize(planned), planned

    async def _plan(
        self, audience: Audience, kind: MessageKind, *, settings: Settings
    ) -> list[ResolvedRecipient]:
        """Resolve, then apply the two rules that only exist per message."""
        resolved = await self.resolver.resolve(audience, kind)

        seen: set[str] = set()
        planned: list[ResolvedRecipient] = []
        for recipient in resolved:
            if recipient.status == "skipped":
                planned.append(recipient)
                continue

            address = (recipient.email or "").strip().lower()
            if address in seen:
                planned.append(replace(recipient, status="skipped", reason=DUPLICATE))
                continue

            # The installation's own switch, checked here rather than at
            # sending time so the board sees the truth *before* pressing send.
            if not may_send(to=address, category="member", settings=settings):
                planned.append(replace(recipient, status="skipped", reason=HELD_BACK))
                continue

            seen.add(address)
            planned.append(recipient)
        return planned

    # --- Queueing ---

    async def queue(
        self,
        *,
        kind: MessageKind,
        subject: str,
        body: str,
        audience: Audience,
        settings: Settings,
    ) -> EmailMessage:
        """Write the message and its recipients, then leave. Sending happens
        in the background loop, which may take minutes for a large club."""
        planned = await self._plan(audience, kind, settings=settings)

        if len(planned) > settings.EMAIL_MAX_RECIPIENTS:
            raise ValidationError(
                f"This selection has {len(planned)} recipients; the limit is "
                f"{settings.EMAIL_MAX_RECIPIENTS}."
            )
        if not any(r.status == "pending" for r in planned):
            # Not an empty gesture: a message nobody receives is almost always
            # the wrong selection, and finding that out afterwards means
            # looking for a mail that never existed.
            #
            # The two reasons are told apart, because they send whoever is
            # standing there to different places: a selection that resolves to
            # nobody is a mistake in the selection, while an installation that
            # holds member mail back is a setting nobody would find by looking
            # at consents.
            if any(r.reason == HELD_BACK for r in planned):
                raise AppError(
                    status_code=422,
                    code="EMAIL_HELD_BACK",
                    message=(
                        "This installation is not sending member mail "
                        f"(EMAIL_DELIVERY={settings.EMAIL_DELIVERY}). Nothing has been queued."
                    ),
                )
            raise ValidationError("This selection reaches nobody. Nothing has been sent.")

        now = datetime.now(UTC)
        message = EmailMessage(
            tenant_id=self.tenant_id,
            kind=kind,
            subject=subject,
            body=body,
            audience=audience.model_dump(mode="json"),
            status="queued",
            sent_by_user_id=self.auth.user_id,
            queued_at=now,
            recipient_count=len(planned),
            created_by=self.auth.user_id,
            updated_by=self.auth.user_id,
        )
        self.session.add(message)
        await self.session.flush()

        self.session.add_all(
            [
                EmailRecipient(
                    tenant_id=self.tenant_id,
                    message_id=message.id,
                    member_id=recipient.member_id,
                    email=(recipient.email or "").strip().lower() or "-",
                    status=recipient.status,
                    reason=recipient.reason,
                )
                for recipient in planned
            ]
        )
        await self.session.flush()

        await record_tenant_action(
            self.session,
            self.auth,
            f"{MESSAGE_TARGET}.queued",
            target_type=MESSAGE_TARGET,
            target_id=message.id,
            changes={
                "kind": kind,
                "subject": subject,
                "recipients": len(planned),
                "pending": sum(1 for r in planned if r.status == "pending"),
            },
        )
        await self.session.refresh(message)
        return message

    async def send_test(self, *, subject: str, body: str, to: str, settings: Settings) -> bool:
        """The same mail to one address, with no recipient rows at all.

        Deliberately not a message: a test that appeared in the history would
        make "what did we send" a question with a footnote.
        """
        return await send_email(
            to=to,
            subject=f"[Test] {subject}",
            body=body,
            category="member",
            settings=settings,
        )

    # --- Reading ---

    async def list_messages(
        self, *, page: int = 1, per_page: int = 20
    ) -> tuple[list[EmailMessage], int]:
        base = select(EmailMessage).where(EmailMessage.tenant_id == self.tenant_id)
        rows = (
            await self.session.execute(
                base.order_by(EmailMessage.queued_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        ).scalars()
        total = (
            await self.session.execute(
                select(func.count())
                .select_from(EmailMessage)
                .where(EmailMessage.tenant_id == self.tenant_id)
            )
        ).scalar_one()
        return list(rows), total

    async def get_message(self, message_id: uuid.UUID) -> EmailMessage:
        message = (
            await self.session.execute(
                select(EmailMessage)
                .where(EmailMessage.tenant_id == self.tenant_id)
                .where(EmailMessage.id == message_id)
            )
        ).scalar_one_or_none()
        if message is None:
            raise NotFoundError("Message not found")
        return message

    async def counts(self, message_id: uuid.UUID) -> dict[str, int]:
        """Delivered, skipped, failed, still waiting — the four numbers a
        board member reads instead of a status word."""
        rows = await self.session.execute(
            select(EmailRecipient.status, func.count())
            .where(EmailRecipient.tenant_id == self.tenant_id)
            .where(EmailRecipient.message_id == message_id)
            .group_by(EmailRecipient.status)
        )
        counted = {status: count for status, count in rows.all()}
        return {
            status: counted.get(status, 0) for status in ("pending", "sent", "failed", "skipped")
        }

    async def list_recipients(
        self,
        message_id: uuid.UUID,
        *,
        status: str | None = None,
        page: int = 1,
        per_page: int = 100,
    ) -> tuple[list[EmailRecipient], int]:
        await self.get_message(message_id)
        base = (
            select(EmailRecipient)
            .where(EmailRecipient.tenant_id == self.tenant_id)
            .where(EmailRecipient.message_id == message_id)
        )
        counter = (
            select(func.count())
            .select_from(EmailRecipient)
            .where(EmailRecipient.tenant_id == self.tenant_id)
            .where(EmailRecipient.message_id == message_id)
        )
        if status:
            base = base.where(EmailRecipient.status == status)
            counter = counter.where(EmailRecipient.status == status)

        rows = (
            await self.session.execute(
                base.order_by(EmailRecipient.email).offset((page - 1) * per_page).limit(per_page)
            )
        ).scalars()
        total = (await self.session.execute(counter)).scalar_one()
        return list(rows), total
