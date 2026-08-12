"""Working through a queued round mail, a few addresses at a time.

## Why a loop and not the request path

Two hundred addresses are two hundred SMTP conversations. Doing them while a
board member waits for their response would time out the request and, worse,
leave nobody able to say how far it got. So pressing "send" writes rows and
returns; this loop turns rows into mail at a pace a mail server tolerates.

Same shape as `app/tasks/retention.py`: a task in the lifespan, no extra
process to deploy, and a Redis `SET NX` so that only one of several Uvicorn
workers takes a batch. Unlike retention, the lock here is not an economy but
a correctness measure — two workers picking the same rows would send the same
mail twice, and there is no unsending.

## What makes a restart harmless

Progress lives in the rows, not in this process. A recipient is `pending`
until it is `sent`, and it is marked the instant its mail is accepted. A
backend killed halfway through a mailing comes back, finds the remaining
`pending` rows, and carries on — the ones already accepted are not looked at
again.

`attempts` is what keeps a permanently broken address from being retried
until the end of time: after `EMAIL_MAX_ATTEMPTS` it is `failed`, with what
the server said, and a human decides what to do about it.
"""

import asyncio
import uuid
from datetime import UTC, datetime

import structlog
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.unsubscribe import unsubscribe_api_url, unsubscribe_url
from app.config import Settings, get_settings
from app.database import async_session_factory
from app.integrations.email import EmailError, send_email
from app.models.message import EmailMessage, EmailRecipient

logger = structlog.get_logger()

#: Held only while a batch is in flight. Long enough that a slow mail server
#: cannot let a second worker in, short enough that a crashed worker does not
#: stall the queue for long.
_LOCK_KEY = "mail-queue:batch"
_LOCK_TTL_SECONDS = 120


async def run_mail_queue(redis: Redis, settings: Settings | None = None) -> None:
    """Forever: take a batch, send it, wait. Cancelled with the app."""
    settings = settings or get_settings()
    while True:
        try:
            await drain_once(redis, settings)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # pragma: no cover - the loop must not die
            # Whatever went wrong, the queue keeps running: a mailing that
            # stops halfway because of one bad round is worse than a slow one.
            logger.error("mail_queue_failed", error=str(exc), exc_info=exc)
        # An empty queue waits the same interval: this is a mail queue, not a
        # chat, and a spare second of latency costs a club nothing.
        await asyncio.sleep(settings.EMAIL_SEND_INTERVAL_SECONDS)


async def drain_once(redis: Redis, settings: Settings) -> int:
    """One batch. Returns how many messages were actually handed over."""
    got_lock = await redis.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL_SECONDS)
    if not got_lock:
        return 0
    try:
        async with async_session_factory() as session:
            count = await send_batch(session, settings)
            await session.commit()
            return count
    finally:
        await redis.delete(_LOCK_KEY)


async def send_batch(session: AsyncSession, settings: Settings) -> int:
    """The unit of work: up to `EMAIL_BATCH_SIZE` addresses of one message.

    One message at a time, oldest first, so a large mailing does not starve
    behind a newer one and two mailings do not interleave in people's inboxes.
    """
    message = (
        await session.execute(
            select(EmailMessage)
            .where(EmailMessage.status.in_(["queued", "sending"]))
            .order_by(EmailMessage.queued_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if message is None:
        return 0

    pending = (
        (
            await session.execute(
                select(EmailRecipient)
                .where(EmailRecipient.message_id == message.id)
                .where(EmailRecipient.status == "pending")
                .order_by(EmailRecipient.email)
                .limit(settings.EMAIL_BATCH_SIZE)
                # Belt to the Redis lock's braces: another worker cannot even
                # read these rows while this transaction holds them.
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )

    if not pending:
        await _finish(session, message)
        return 0

    if message.status != "sending":
        message.status = "sending"

    sent = 0
    for recipient in pending:
        recipient.attempts += 1
        body, headers = _for_recipient(message, recipient, settings)
        try:
            delivered = await send_email(
                to=recipient.email,
                subject=message.subject,
                body=body,
                category="member",
                settings=settings,
                headers=headers,
            )
        except EmailError as exc:
            # One address failing is one address failing. The rest of the
            # batch still goes out, and this row is tried again next round
            # until it runs out of attempts.
            recipient.error = str(exc)[:500]
            if recipient.attempts >= settings.EMAIL_MAX_ATTEMPTS:
                recipient.status = "failed"
            continue

        if not delivered:
            # The installation is holding member mail back, or has no SMTP at
            # all. Not a failure of this address — a decision above it.
            recipient.status = "skipped"
            recipient.reason = "held_back"
            continue

        recipient.status = "sent"
        recipient.sent_at = datetime.now(UTC)
        recipient.error = None
        sent += 1

    await session.flush()
    await _finish(session, message)
    logger.info("mail_batch_sent", message_id=str(message.id), sent=sent, batch=len(pending))
    return sent


def _for_recipient(
    message: EmailMessage, recipient: EmailRecipient, settings: Settings
) -> tuple[str, dict[str, str]]:
    """The body this person gets, and the headers that go with it.

    A newsletter carries a way out — in the text, because that is where a
    person looks, and in `List-Unsubscribe`, because that is where a mail
    client looks. Leaving the header off is not a formality: without it the
    unsubscribe button in Gmail and Outlook disappears, people press "spam"
    instead, and the club's whole domain pays for it.

    A duty notice carries neither. There is nothing to unsubscribe from — the
    invitation to the general meeting is not a mailing — and offering a way
    out of it would promise something the club cannot keep.
    """
    if message.kind != "newsletter" or recipient.member_id is None:
        return message.body, {}

    link = unsubscribe_url(recipient.member_id, settings)
    body = (
        f"{message.body}\n\n"
        "-- \n"
        "Sie erhalten diese Nachricht, weil Sie dem Newsletter Ihres Vereins "
        "zugestimmt haben.\n"
        f"Abmelden: {link}\n"
    )
    headers = {
        "List-Unsubscribe": f"<{unsubscribe_api_url(recipient.member_id, settings)}>",
        # RFC 8058: lets the client unsubscribe with one press, without ever
        # showing the page. Our POST endpoint needs no body, which is exactly
        # what a one-click client sends.
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    return body, headers


async def _finish(session: AsyncSession, message: EmailMessage) -> None:
    """Close the message once nothing is left waiting.

    `failed` only when *every* address failed — anything less is partial, and
    a partial mailing that calls itself failed sends somebody looking for a
    problem that hit three of two hundred.
    """
    remaining = (
        await session.execute(
            select(func.count())
            .select_from(EmailRecipient)
            .where(EmailRecipient.message_id == message.id)
            .where(EmailRecipient.status == "pending")
        )
    ).scalar_one()
    if remaining:
        return

    delivered = (
        await session.execute(
            select(func.count())
            .select_from(EmailRecipient)
            .where(EmailRecipient.message_id == message.id)
            .where(EmailRecipient.status == "sent")
        )
    ).scalar_one()

    message.status = "sent" if delivered else "failed"
    message.finished_at = datetime.now(UTC)
    await session.flush()


async def message_progress(session: AsyncSession, message_id: uuid.UUID) -> dict[str, int]:
    """Counts per status, for tests and for the detail endpoint."""
    rows = await session.execute(
        select(EmailRecipient.status, func.count())
        .where(EmailRecipient.message_id == message_id)
        .group_by(EmailRecipient.status)
    )
    return {status: count for status, count in rows.all()}
