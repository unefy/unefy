"""Outbound email.

Deliberately thin: a single `send_email` over SMTP, because SMTP is the one
transport every self-hoster already has. SaaS deployments point the same
settings at a relay, so no code branches on deployment mode.

Without `SMTP_HOST` nothing is sent and the message is logged instead. That
keeps local development working without a mail server — and makes a
half-configured deployment visible in the log rather than silently dropping
mail.
"""

from email.message import EmailMessage

import aiosmtplib
import structlog

from app.config import Settings, get_settings

logger = structlog.get_logger()


class EmailError(Exception):
    """Raised when a message could not be handed to the mail server."""


def _build(to: str, subject: str, body: str, settings: Settings) -> EmailMessage:
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    return message


async def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    settings: Settings | None = None,
) -> None:
    """Send a plain-text message.

    Raises `EmailError` when SMTP is configured but unreachable, so callers can
    decide whether that is fatal. Callers that must not fail because of mail
    (magic link requests, which would otherwise leak whether an address exists)
    should catch it.
    """
    settings = settings or get_settings()

    if not settings.SMTP_HOST:
        # No transport configured — log the full message so the flow stays
        # usable in development. Never reached in a deployment with SMTP set.
        logger.warning("email_not_sent_no_smtp_host", to=to, subject=subject, body=body)
        return

    message = _build(to, subject, body, settings)

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

    logger.info("email_sent", subject=subject)
