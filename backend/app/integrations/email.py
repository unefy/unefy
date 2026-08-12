"""Outbound email, and the switch that stops it.

Deliberately thin: a single `send_email` over SMTP, because SMTP is the one
transport every self-hoster already has. SaaS deployments point the same
settings at a relay, so no code branches on deployment mode.

Without `SMTP_HOST` nothing is sent and the message is logged instead. That
keeps local development working without a mail server — and makes a
half-configured deployment visible in the log rather than silently dropping
mail.

## The switch

An installation can hold real member addresses long before it is ready to
write to them — a club's data is imported for testing weeks before the first
mail is meant to go out. One accidental round mail to 300 people cannot be
recalled, and it is the kind of mistake that ends a pilot.

So delivery is a setting with three positions (`EMAIL_DELIVERY`):

| Wert | Was rausgeht |
|---|---|
| `auth_only` | nur Anmeldelinks und Anmeldecodes — **Standard** |
| `all` | alles |
| `none` | nichts, auch keine Anmeldung |

Every message therefore states its `category`: `auth` for the two login
mails, `member` for everything that reaches somebody who did not just ask for
it. The parameter is required, so a new kind of mail has to answer the
question before it can be sent at all.

`EMAIL_ALLOWLIST` is the escape hatch for testing: addresses (or `@domain`
entries) on it receive `member` mail even in `auth_only`. In `none` nothing
leaves, allowlist included — that position exists for the moment when the
answer has to be "definitely nothing".

The default is the careful one. A production stack sets `EMAIL_DELIVERY=all`
in its environment (see `docker-compose.prod.yml`), which is a deliberate act;
forgetting the setting costs a club its newsletter, forgetting the other
direction costs it its members' trust.
"""

from email.message import EmailMessage
from typing import Literal

import aiosmtplib
import structlog

from app.config import Settings, get_settings

logger = structlog.get_logger()

#: What kind of message this is, from the delivery switch's point of view.
#:
#: `auth` is only ever the login link and the login code — mail somebody is
#: waiting for, seconds after asking for it. Everything else is `member`,
#: including invitations: they arrive unannounced in a real person's inbox.
EmailCategory = Literal["auth", "member"]


class EmailError(Exception):
    """Raised when a message could not be handed to the mail server."""


def may_send(
    *,
    to: str,
    category: EmailCategory,
    settings: Settings,
) -> bool:
    """Whether this message is allowed out at all.

    Pure, and the only place the rule lives. Kept separate from the sending so
    it can be read — and tested — without a mail server in the room.
    """
    mode = settings.EMAIL_DELIVERY
    if mode == "none":
        return False
    if mode == "all" or category == "auth":
        return True
    return _on_allowlist(to, settings.EMAIL_ALLOWLIST)


def _on_allowlist(to: str, allowlist: list[str]) -> bool:
    """`someone@example.org` matches itself; `@example.org` matches the domain."""
    address = to.strip().lower()
    for entry in allowlist:
        # Stripped and lower-cased because this is typed into an .env by hand.
        # An empty entry — a trailing comma — needs no branch of its own: it
        # equals no address and is not a domain.
        candidate = entry.strip().lower()
        if candidate.startswith("@"):
            if address.endswith(candidate):
                return True
        elif address == candidate:
            return True
    return False


def _build(
    to: str,
    subject: str,
    body: str,
    settings: Settings,
    headers: dict[str, str] | None = None,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    for name, value in (headers or {}).items():
        message[name] = value
    message.set_content(body)
    return message


async def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    category: EmailCategory,
    settings: Settings | None = None,
    headers: dict[str, str] | None = None,
) -> bool:
    """Send a plain-text message. Returns False when it was held back.

    Held back is not an error: the caller asked for something the installation
    currently does not do, and the request itself succeeded. A round mail
    records such a recipient as skipped rather than failed.

    Raises `EmailError` when SMTP is configured, delivery is allowed, and the
    server is unreachable — so callers can decide whether that is fatal.
    Callers that must not fail because of mail (magic link requests, which
    would otherwise leak whether an address exists) should catch it.
    """
    settings = settings or get_settings()

    if not may_send(to=to, category=category, settings=settings):
        # Logged without the body: this is the normal state of a test system,
        # not an incident, and the log should not become a copy of the mail.
        logger.info(
            "email_held_back",
            subject=subject,
            category=category,
            mode=settings.EMAIL_DELIVERY,
        )
        return False

    if not settings.SMTP_HOST:
        # No transport configured — log the full message so the flow stays
        # usable in development. Never reached in a deployment with SMTP set.
        logger.warning("email_not_sent_no_smtp_host", to=to, subject=subject, body=body)
        return False

    message = _build(to, subject, body, settings, headers)

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=settings.SMTP_STARTTLS,
        )
    except (aiosmtplib.SMTPException, OSError) as exc:
        # The address is deliberately not logged at error level: a bounce log
        # full of addresses is a data-protection problem of its own.
        logger.error("email_send_failed", subject=subject, error=str(exc))
        raise EmailError(str(exc)) from exc

    logger.info("email_sent", subject=subject, category=category)
    return True
