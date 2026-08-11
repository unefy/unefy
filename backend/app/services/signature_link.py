"""The short-lived link that lets somebody sign one document on their phone.

The board member who issues a document asks for a link; whoever opens it draws
a signature with a finger and it lands on that document. The chair does not
need an account on the tablet, and nobody has to walk a printout across the
village.

The link is a bearer credential handed around outside our control — put on a
screen, scanned, maybe photographed by accident — so it is built like the
magic link and then made stricter: 32 random bytes, stored only as a hash,
fifteen minutes, and it names exactly one document. Signing consumes it.

**It is not a signature the club keeps.** Nothing here can be replayed onto a
second document, and there is no club-wide signature graphic to steal — see
`IssuedDocument.signature_png`.
"""

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass

from app.redis import get_redis

_KEY_PREFIX = "document-signature:"

#: Long enough to walk to the noticeboard and unlock a phone, short enough that
#: a link left on a screen is worthless by the time the room is empty.
TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class SignatureTarget:
    """What a token stands for. Never more than one document."""

    tenant_id: uuid.UUID
    document_id: uuid.UUID


def _hash(token: str) -> str:
    """Stored hashed, so a Redis dump is not a stack of working links.

    Plain SHA-256 without a salt, as for the magic link: the token already
    carries its own entropy, and a keyed hash would only add a secret to
    rotate.
    """
    return hashlib.sha256(token.encode()).hexdigest()


async def issue(target: SignatureTarget) -> str:
    token = secrets.token_urlsafe(32)
    await get_redis().set(
        f"{_KEY_PREFIX}{_hash(token)}",
        json.dumps({"tenant_id": str(target.tenant_id), "document_id": str(target.document_id)}),
        ex=TTL_SECONDS,
    )
    return token


async def peek(token: str) -> SignatureTarget | None:
    """Resolve a token without spending it — the signing page has to render
    before anybody has drawn anything."""
    stored = await get_redis().get(f"{_KEY_PREFIX}{_hash(token)}")
    return _decode(stored)


async def consume(token: str) -> SignatureTarget | None:
    """Resolve and spend. Deleted before returning, so two taps on a slow
    connection cannot sign twice."""
    redis = get_redis()
    key = f"{_KEY_PREFIX}{_hash(token)}"
    stored = await redis.get(key)
    if stored is None:
        return None
    await redis.delete(key)
    return _decode(stored)


def _decode(stored: object) -> SignatureTarget | None:
    if stored is None:
        return None
    raw = stored.decode() if isinstance(stored, bytes) else str(stored)
    data = json.loads(raw)
    return SignatureTarget(
        tenant_id=uuid.UUID(data["tenant_id"]),
        document_id=uuid.UUID(data["document_id"]),
    )
