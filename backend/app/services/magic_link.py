"""Passwordless sign-in via a one-time link.

The token is a bearer credential that lives in an inbox, so it is treated like
one: 32 random bytes, short-lived, single-use, and stored only as a hash. A
Redis dump therefore does not hand out working links.
"""

import hashlib
import secrets

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.integrations.email import EmailError, send_email
from app.models.user import User
from app.redis import get_redis

logger = structlog.get_logger()

_KEY_PREFIX = "magic-link:"


def _hash(token: str) -> str:
    """Tokens are stored hashed — Redis never holds a usable credential.

    Plain SHA-256 without a salt is deliberate: the token already carries 256
    bits of entropy, so there is nothing to brute-force, and a keyed hash would
    only add a secret to rotate.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def issue_token(email: str, settings: Settings) -> str:
    """Create a single-use token for `email` and store its hash."""
    token = secrets.token_urlsafe(32)
    redis = get_redis()
    await redis.set(
        f"{_KEY_PREFIX}{_hash(token)}",
        normalize_email(email),
        ex=settings.MAGIC_LINK_TTL_SECONDS,
    )
    return token


async def consume_token(token: str) -> str | None:
    """Redeem a token and return the email it was issued for.

    Deletes the entry before returning, so a link works exactly once even if it
    is opened twice in quick succession (mail scanners routinely do this).
    """
    redis = get_redis()
    key = f"{_KEY_PREFIX}{_hash(token)}"
    email = await redis.get(key)
    if email is None:
        return None
    await redis.delete(key)
    return email if isinstance(email, str) else email.decode()


async def send_magic_link(email: str, token: str, settings: Settings) -> None:
    """Mail the sign-in link.

    Swallows delivery failures on purpose: the caller answers 200 regardless of
    whether the address exists, and a 500 here would reintroduce exactly the
    account-enumeration signal that the flat response avoids.
    """
    link = f"{settings.BACKEND_URL}/api/v1/auth/magic-link/verify?token={token}"
    minutes = settings.MAGIC_LINK_TTL_SECONDS // 60

    try:
        await send_email(
            to=email,
            subject="Ihr Anmeldelink für unefy",
            body=(
                "Hallo,\n\n"
                "mit diesem Link melden Sie sich bei unefy an:\n\n"
                f"{link}\n\n"
                f"Der Link ist {minutes} Minuten gültig und funktioniert nur einmal.\n\n"
                "Wenn Sie keine Anmeldung angefordert haben, ignorieren Sie diese "
                "E-Mail — ohne den Link passiert nichts.\n"
            ),
            settings=settings,
        )
    except EmailError:
        logger.error("magic_link_delivery_failed")


# --- Mobile: one-time code instead of a link -----------------------------------
#
# A link that opens the backend in a browser is the wrong shape for an app; a
# short code the person copies from their inbox is the established mobile
# answer. Six digits are only ~20 bits, so unlike the link the code leans on
# its guards: same short TTL, single mailbox, and a hard attempt cap.

_OTP_KEY_PREFIX = "magic-otp:"
_OTP_TRIES_PREFIX = "magic-otp-tries:"

#: After this many wrong guesses the code dies. Five is generous for typos and
#: hopeless for guessing one in a million within the TTL.
OTP_MAX_ATTEMPTS = 5


async def issue_otp(email: str, settings: Settings) -> str:
    """Create a one-time login code for `email` and store its hash.

    Re-requesting replaces the previous code — at most one is ever live per
    mailbox, which also resets nothing for an attacker (the attempt counter
    only ever tightens until the TTL runs out).
    """
    code = f"{secrets.randbelow(1_000_000):06d}"
    redis = get_redis()
    normalized = normalize_email(email)
    await redis.set(
        f"{_OTP_KEY_PREFIX}{normalized}",
        _hash(code),
        ex=settings.MAGIC_LINK_TTL_SECONDS,
    )
    return code


async def consume_otp(email: str, code: str, settings: Settings) -> bool:
    """Redeem a login code. True exactly once, for the right mailbox and code."""
    redis = get_redis()
    normalized = normalize_email(email)
    key = f"{_OTP_KEY_PREFIX}{normalized}"
    stored = await redis.get(key)
    if stored is None:
        return False
    stored_hash = stored if isinstance(stored, str) else stored.decode()

    tries_key = f"{_OTP_TRIES_PREFIX}{normalized}"
    tries = await redis.incr(tries_key)
    await redis.expire(tries_key, settings.MAGIC_LINK_TTL_SECONDS)
    if tries > OTP_MAX_ATTEMPTS:
        # Too many guesses: kill the code itself, not just this attempt.
        await redis.delete(key)
        logger.warning("magic_otp_attempts_exhausted")
        return False

    if not secrets.compare_digest(stored_hash, _hash(code)):
        return False

    await redis.delete(key)
    await redis.delete(tries_key)
    return True


async def send_login_code(email: str, code: str, settings: Settings) -> None:
    """Mail the login code. Swallows failures — see `send_magic_link`."""
    minutes = settings.MAGIC_LINK_TTL_SECONDS // 60
    try:
        await send_email(
            to=email,
            subject=f"{code} ist Ihr unefy-Anmeldecode",
            body=(
                "Hallo,\n\n"
                "Ihr Anmeldecode für die unefy-App lautet:\n\n"
                f"    {code}\n\n"
                f"Der Code ist {minutes} Minuten gültig und funktioniert nur einmal.\n\n"
                "Wenn Sie keine Anmeldung angefordert haben, ignorieren Sie diese "
                "E-Mail — ohne den Code passiert nichts.\n"
            ),
            settings=settings,
        )
    except EmailError:
        logger.error("magic_otp_delivery_failed")


async def resolve_user(session: AsyncSession, email: str) -> User:
    """Find the account for `email`, creating one on first sign-in.

    Receiving the link proves control of the mailbox, so the address counts as
    verified — the same standard the Google flow applies.
    """
    normalized = normalize_email(email)
    user = (
        await session.execute(select(User).where(User.email == normalized))
    ).scalar_one_or_none()

    if user is None:
        user = User(email=normalized, name=normalized, email_verified=True)
        session.add(user)
        await session.flush()
        logger.info("user_created", user_id=str(user.id), method="magic_link")
    elif not user.email_verified:
        user.email_verified = True
        await session.flush()

    return user
