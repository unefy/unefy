"""The board's side of the join form: read applications, decide on them."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.schemas.application import (
    ApplicationDecision,
    ApplicationDetailResponse,
    ApplicationResponse,
)
from app.schemas.member import MemberResponse
from app.services.application import ApplicationService

router = APIRouter()


def _to_response(application: Any) -> dict[str, Any]:
    payload = ApplicationResponse.model_validate(application).model_dump(mode="json")
    payload["has_sepa_mandate"] = application.sepa_mandate_date is not None
    return payload


@router.get("")
async def list_applications(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    status: str | None = Query(default=None, pattern="^(pending|accepted|rejected)$"),
) -> dict[str, Any]:
    """Applications, newest first. Bank details are not in this list."""
    service = ApplicationService(session, auth.tenant)
    applications = await service.list(status=status)
    return {"data": [_to_response(a) for a in applications]}


@router.get("/{application_id}")
async def get_application(
    application_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """One application, with the bank details — this is where deciding happens."""
    service = ApplicationService(session, auth.tenant)
    application = await service.get(application_id)
    payload = ApplicationDetailResponse.model_validate(application).model_dump(mode="json")
    payload["has_sepa_mandate"] = application.sepa_mandate_date is not None
    return {"data": payload}


@router.post("/{application_id}/accept")
async def accept_application(
    application_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Admit the applicant and return the member that was created.

    Returns the member rather than the application because that is what the
    caller does next: the board opens the new member's page.
    """
    service = ApplicationService(session, auth.tenant)
    member = await service.accept(application_id, decided_by=auth.user_id)
    return {"data": MemberResponse.model_validate(member).model_dump(mode="json")}


@router.post("/{application_id}/reject")
async def reject_application(
    application_id: uuid.UUID,
    data: ApplicationDecision,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Turn an application down. The note is the club's record, not a message."""
    service = ApplicationService(session, auth.tenant)
    application = await service.reject(application_id, decided_by=auth.user_id, note=data.note)
    return {"data": _to_response(application)}
