"""`/api/v1/messages` — the club's round mail.

Writing is the committee's. There is no read access for members: what the
club sent to whom is board business, and a member's own copy is in their
inbox.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.schemas.base import BaseSchema
from app.schemas.message import Audience, MessageKind, RecipientPreview
from app.services.message import MessageService

router = APIRouter()

BOARD = ("owner", "admin", "board")

#: How many resolved recipients travel with a preview. The counts are the
#: point; the names are there so somebody can spot "that is not the list I
#: meant" — and a club of 800 does not need 800 rows to see that.
PREVIEW_LIMIT = 50


class PreviewRequest(BaseSchema):
    kind: MessageKind
    audience: Audience


class MessageRequest(BaseSchema):
    kind: MessageKind
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=20000)
    audience: Audience


class TestRequest(BaseSchema):
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=20000)
    to: str = Field(min_length=3, max_length=255)


def _service(auth: AuthContext, session: AsyncSession) -> MessageService:
    return MessageService(session, auth)


def _message(message: Any, counts: dict[str, int]) -> dict[str, Any]:
    return {
        "id": str(message.id),
        "kind": message.kind,
        "subject": message.subject,
        "body": message.body,
        "audience": message.audience,
        "status": message.status,
        "recipient_count": message.recipient_count,
        "queued_at": message.queued_at.isoformat(),
        "finished_at": message.finished_at.isoformat() if message.finished_at else None,
        "counts": counts,
    }


@router.post("/preview")
async def preview_message(
    data: PreviewRequest,
    auth: AuthContext = Depends(require_role(*BOARD)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Who this would reach, before anything is written.

    Runs the same resolution the sending does, so the number here is the
    number that goes out — including the ones held back by the installation's
    own delivery switch.
    """
    summary, recipients = await _service(auth, session).preview(
        data.audience, data.kind, settings=settings
    )
    return {
        "data": {
            "summary": summary.model_dump(mode="json"),
            "recipients": [
                RecipientPreview.model_validate(r, from_attributes=True).model_dump(mode="json")
                for r in recipients[:PREVIEW_LIMIT]
            ],
            "truncated": len(recipients) > PREVIEW_LIMIT,
        }
    }


@router.post("", status_code=201)
async def queue_message(
    data: MessageRequest,
    auth: AuthContext = Depends(require_role(*BOARD)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """Queue the message. Sending happens in the background, in batches."""
    service = _service(auth, session)
    message = await service.queue(
        kind=data.kind,
        subject=data.subject,
        body=data.body,
        audience=data.audience,
        settings=settings,
    )
    return {"data": _message(message, await service.counts(message.id))}


@router.post("/test")
async def send_test_message(
    data: TestRequest,
    auth: AuthContext = Depends(require_role(*BOARD)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """The same mail to one address, so somebody can read it before 200 do.

    `delivered: false` is a real answer, not an error: an installation that
    holds member mail back holds the test back too, and saying "sent" would
    be a lie the board would only discover by waiting for it.
    """
    delivered = await _service(auth, session).send_test(
        subject=data.subject, body=data.body, to=data.to, settings=settings
    )
    return {"data": {"delivered": delivered}}


@router.get("")
async def list_messages(
    auth: AuthContext = Depends(require_role(*BOARD)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    service = _service(auth, session)
    messages, total = await service.list_messages(page=page, per_page=per_page)
    return {
        "data": [_message(m, await service.counts(m.id)) for m in messages],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        },
    }


@router.get("/{message_id}")
async def get_message(
    message_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(*BOARD)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    service = _service(auth, session)
    message = await service.get_message(message_id)
    return {"data": _message(message, await service.counts(message_id))}


@router.get("/{message_id}/recipients")
async def list_recipients(
    message_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(*BOARD)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    status: str | None = Query(default=None, pattern="^(pending|sent|failed|skipped)$"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    """The rows, filterable — the screen for "who did not get it and why"."""
    recipients, total = await _service(auth, session).list_recipients(
        message_id, status=status, page=page, per_page=per_page
    )
    return {
        "data": [
            {
                "id": str(r.id),
                "member_id": str(r.member_id) if r.member_id else None,
                "email": r.email,
                "status": r.status,
                "reason": r.reason,
                "error": r.error,
                "attempts": r.attempts,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            }
            for r in recipients
        ],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        },
    }
