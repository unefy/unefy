"""Managing who can sign in to a club.

Everything here is restricted to `owner` and `admin`: handing out access is the
one action that can escalate someone else's rights, so it stays with the two
roles that already have them.
"""

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.core.rate_limit import RateLimit
from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.services.club_access import ASSIGNABLE_ROLES, ClubAccessService

logger = structlog.get_logger()
router = APIRouter()

_ROLE_PATTERN = f"^({'|'.join(ASSIGNABLE_ROLES)})$"


class InviteRequest(BaseModel):
    """Either an address, or a member whose address is used.

    With `member_id` the address comes from the member record and any `email`
    in the request is ignored — see the service for why.
    """

    email: EmailStr | None = None
    role: str = Field(default="member", pattern=_ROLE_PATTERN)
    member_id: uuid.UUID | None = None


class LinkRequest(BaseModel):
    member_id: uuid.UUID
    user_id: uuid.UUID


class RoleUpdate(BaseModel):
    role: str = Field(pattern=_ROLE_PATTERN)


class ActiveUpdate(BaseModel):
    is_active: bool


def _tenant_id(auth: AuthContext) -> uuid.UUID:
    """A club-scoped session always carries a tenant; onboarding ones do not."""
    if auth.tenant_id is None:
        raise ValidationError("No club selected")
    return auth.tenant_id


@router.get("")
async def list_access(
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Accounts with access plus the invitations still outstanding."""
    service = ClubAccessService(session)
    tenant_id = _tenant_id(auth)
    return {
        "data": {
            "members": await service.list_members(tenant_id),
            "invitations": await service.list_invitations(tenant_id),
        }
    }


@router.post(
    "/invitations",
    status_code=201,
    dependencies=[
        # Invitations send mail to an address the club chooses, so the endpoint
        # is a spam vector if left unbounded.
        Depends(RateLimit(limit=20, window=3600, by="user", scope="club-invite")),
    ],
)
async def invite(
    data: InviteRequest,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    invitation = await ClubAccessService(session).invite(
        tenant_id=_tenant_id(auth),
        email=data.email,
        role=data.role,
        invited_by=auth.user_id,
        settings=settings,
        member_id=data.member_id,
    )
    return {"data": invitation}


@router.post("/links", status_code=201)
async def link_member(
    data: LinkRequest,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Bind an existing club account to a member record.

    The path for people who can already sign in — the invitation flow refuses
    them, and without this the founder can never reach their own member data.
    """
    return {
        "data": await ClubAccessService(session).link_member(
            _tenant_id(auth), data.member_id, data.user_id
        )
    }


@router.delete("/links/{member_id}", status_code=204)
async def unlink_member(
    member_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    await ClubAccessService(session).unlink_member(_tenant_id(auth), member_id)


@router.delete("/invitations/{invitation_id}", status_code=204)
async def revoke_invitation(
    invitation_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    await ClubAccessService(session).revoke_invitation(_tenant_id(auth), invitation_id)


@router.patch("/members/{user_id}")
async def update_role(
    user_id: uuid.UUID,
    data: RoleUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    return {"data": await ClubAccessService(session).set_role(_tenant_id(auth), user_id, data.role)}


@router.patch("/members/{user_id}/active")
async def update_active(
    user_id: uuid.UUID,
    data: ActiveUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    return {
        "data": await ClubAccessService(session).set_active(
            _tenant_id(auth), user_id, data.is_active
        )
    }
