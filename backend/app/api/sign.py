"""Signing one document on whatever device is to hand — unauthenticated, by link.

Lives outside `/api/v1` like `/join` and `/verify`: it is the back end of a
page somebody opens on a phone, not an API for our own clients. The board
member who issued the document asks for a link, puts the QR on the screen, and
the chair signs with a finger. Nobody needs an account on that phone, and
nobody has to walk a printout across the village.

The link *is* the authorisation, so it is built to be worth little: 32 random
bytes, stored hashed, fifteen minutes, one named document, spent on signing.
See `services/signature_link`.

The page shows the document's full text, and that is deliberate — you cannot
ask somebody to sign something they are not allowed to read. What protects it
is that the link is unguessable and short-lived, not that the content is
withheld.
"""

import base64
import binascii
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.rate_limit import RateLimit
from app.database import get_db_session
from app.models.document import MAX_SIGNATURE_BYTES
from app.models.member import Member
from app.models.tenant import Tenant
from app.schemas.document import SignatureSubmit
from app.services import signature_link
from app.services.document import DocumentService

router = APIRouter(tags=["sign"])

#: Base64 carries about a third more than the bytes it encodes.
_MAX_ENCODED = MAX_SIGNATURE_BYTES * 4 // 3 + 16


@router.get(
    "/sign/{token}",
    # A page being opened, possibly twice because the first tap missed. Tight
    # enough that the token space cannot be walked.
    dependencies=[Depends(RateLimit(limit=20, window=60, scope="sign-page"))],
)
async def signing_page(
    token: str,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """What the signing page shows: the club, the document, and its text."""
    target = await signature_link.peek(token)
    if target is None:
        raise NotFoundError("This link is no longer valid")

    document = await DocumentService(session, target.tenant_id).get_document(target.document_id)
    if document.signed_at is not None or document.revoked_at is not None:
        raise NotFoundError("This link is no longer valid")

    tenant = await session.get(Tenant, target.tenant_id)
    member = await session.get(Member, document.member_id)
    zone = ZoneInfo(tenant.timezone if tenant else "Europe/Berlin")

    return {
        "data": {
            "club_name": tenant.name if tenant else "",
            "title": document.title,
            "body": document.body,
            "member_name": f"{member.first_name} {member.last_name}" if member else "",
            "issued_on": document.issued_at.astimezone(zone).date().isoformat(),
        }
    }


@router.post(
    "/sign/{token}",
    # Signing is a single act by one person; anything faster is not a person.
    dependencies=[Depends(RateLimit(limit=10, window=60, scope="sign-submit"))],
)
async def sign_document(
    token: str,
    data: SignatureSubmit,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Attach the drawn signature and spend the link.

    The token is consumed first: if the write then fails, the link is gone and
    the board issues a new one. The other order would leave a link that worked
    twice.
    """
    if len(data.signature_png) > _MAX_ENCODED:
        raise ValidationError("Signature too large")

    target = await signature_link.consume(token)
    if target is None:
        raise NotFoundError("This link is no longer valid")

    try:
        png = base64.b64decode(_strip_data_url(data.signature_png), validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValidationError("Signature could not be read") from error

    await DocumentService(session, target.tenant_id).attach_signature(target.document_id, png)
    return {"data": {"signed": True}}


def _strip_data_url(value: str) -> str:
    """A canvas hands out `data:image/png;base64,…`; only the tail is data."""
    marker = "base64,"
    index = value.find(marker)
    return value[index + len(marker) :] if index != -1 else value
