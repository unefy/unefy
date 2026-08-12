"""The link at the bottom of a newsletter.

Outside `/api/v1` on purpose, like `join` and `verify`: this URL is printed
into mail that sits in inboxes for years, and a printed thing must outlive
API versioning.

No session, no club context — the token carries the member. What it can do is
exactly one thing, and the worst it can do is unsubscribe somebody from a
newsletter they can re-subscribe to on their own page.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.core.unsubscribe import verify
from app.database import get_db_session
from app.models.member import Member
from app.schemas.consent import ConsentRecord
from app.services.consent import ConsentService

router = APIRouter(prefix="/unsubscribe", tags=["unsubscribe"])

NEWSLETTER = "newsletter"


async def _member(token: str, session: AsyncSession, settings: Settings) -> Member:
    member_id = verify(token, settings.SESSION_SECRET)
    if member_id is None:
        raise NotFoundError("This link is not valid")
    member = (
        await session.execute(
            select(Member).where(Member.id == member_id).where(Member.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if member is None:
        raise NotFoundError("This link is not valid")
    return member


@router.get("/{token}")
async def show(
    token: str,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Who is about to be unsubscribed, so the page can say so.

    Reading only. Mail clients and scanners follow links in the background,
    and a GET that unsubscribed would take people off the list who never
    clicked anything.
    """
    member = await _member(token, session, settings)
    return {
        "data": {
            "first_name": member.first_name,
            "last_name": member.last_name,
            "email": member.email,
        }
    }


@router.post("/{token}", status_code=200)
async def unsubscribe(
    token: str,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Withdraw the newsletter consent.

    Written through the ordinary consent ledger — the same append-only record
    the member's own page writes to, with source `self`, because that is who
    acted. A withdrawal recorded anywhere else would be invisible to the
    screen that is supposed to show it.
    """
    member = await _member(token, session, settings)
    await ConsentService(session, member.tenant_id).record(
        member.id,
        ConsentRecord(kind=NEWSLETTER, granted=False),
        source="self",
        recorded_by=None,
    )
    return {"data": {"unsubscribed": True}}


def unsubscribe_api_url(member_id: uuid.UUID, settings: Settings) -> str:
    """The URL a *mail client* posts to for one-click unsubscribe.

    The backend, not the web app: RFC 8058 has the client POST here without
    ever showing a page, and a Next.js route would only forward it.
    """
    from app.core.unsubscribe import sign

    token = sign(member_id, settings.SESSION_SECRET)
    return f"{settings.BACKEND_URL.rstrip('/')}/unsubscribe/{token}"


def unsubscribe_url(member_id: uuid.UUID, settings: Settings) -> str:
    """The link that goes into the mail. Points at the web app, which shows a
    page and calls back here — a member clicking a link should read a sentence,
    not a JSON object."""
    from app.core.unsubscribe import sign

    token = sign(member_id, settings.SESSION_SECRET)
    return f"{settings.WEB_APP_URL.rstrip('/')}/unsubscribe/{token}"
