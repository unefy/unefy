import math
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.preconditions import require_if_match, set_etag
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user, require_role
from app.repositories.member import MemberRepository
from app.schemas.member import (
    FederationMembershipResponse,
    MemberBulkDelete,
    MemberCreate,
    MemberDirectoryEntry,
    MemberResponse,
    MemberUpdate,
)
from app.services.member import MemberService

router = APIRouter()


def _get_service(session: AsyncSession, auth: AuthContext) -> MemberService:
    repo = MemberRepository(session, auth.tenant)
    return MemberService(repo, session)


@router.get("")
async def list_members(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(
        default="last_name",
        pattern=(
            "^(last_name|first_name|member_number|email|status|category|joined_at|created_at)$"
        ),
    ),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
) -> dict[str, Any]:
    """List members with pagination, filtering, and search."""
    service = _get_service(session, auth)
    offset = (page - 1) * per_page

    members = await service.list(
        offset=offset,
        limit=per_page,
        status=status,
        category=category,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    total = await service.count(
        status=status,
        category=category,
        search=search,
    )
    status_counts = await service.status_counts(search=search)

    return {
        "data": [MemberResponse.model_validate(m).model_dump() for m in members],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total > 0 else 1,
            "status_counts": status_counts,
        },
    }


@router.get("/me")
async def get_my_member(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """The caller's own member record.

    Self-service, so it takes no role: every signed-in member of the tenant may
    read their own row and nobody else's. Declared before `/{member_id}` because
    that route parses its path segment as a UUID and would reject "me".
    """
    repo = MemberRepository(session, auth.tenant)
    member = await repo.get_by_user_id(auth.user_id)
    if member is None:
        # A user account without a linked member row is a normal state — board
        # members administer clubs they are not themselves a member of.
        raise NotFoundError("No member record is linked to this account")
    return {"data": MemberResponse.model_validate(member).model_dump(mode="json")}


@router.get("/directory")
async def list_member_directory(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
) -> dict[str, Any]:
    """The club directory as a member sees it.

    Open to every signed-in member, unlike the administrative list above, and
    narrow in return: active members, names and category only. See
    `MemberDirectoryEntry` for why that narrowing is a separate schema.
    """
    repo = MemberRepository(session, auth.tenant)
    offset = (page - 1) * per_page
    members = await repo.directory(offset=offset, limit=per_page, search=search)
    total = await repo.directory_count(search=search)
    return {
        "data": [
            MemberDirectoryEntry.model_validate(member).model_dump(mode="json")
            for member in members
        ],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total > 0 else 1,
        },
    }


@router.get("/{member_id}")
async def get_member(
    member_id: uuid.UUID,
    response: Response,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Get a single member. The ETag is the If-Match ticket for later writes."""
    service = _get_service(session, auth)
    member = await service.get(member_id)

    if member is None:
        raise NotFoundError("Member not found")

    set_etag(response, member)
    return {"data": MemberResponse.model_validate(member).model_dump()}


@router.post("", status_code=201)
async def create_member(
    data: MemberCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Create a new member. Member number is auto-generated."""
    service = _get_service(session, auth)
    member = await service.create(data, created_by=auth.user_id)

    return {"data": MemberResponse.model_validate(member).model_dump()}


@router.patch("/{member_id}")
async def update_member(
    member_id: uuid.UUID,
    data: MemberUpdate,
    request: Request,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Update a member. Honours If-Match — absent, last write wins as ever."""
    service = _get_service(session, auth)
    existing = await service.get(member_id)
    if existing is None:
        raise NotFoundError("Member not found")
    require_if_match(
        request, existing, MemberResponse.model_validate(existing).model_dump(mode="json")
    )

    member = await service.update(member_id, data, updated_by=auth.user_id)

    if member is None:
        raise NotFoundError("Member not found")

    return {"data": MemberResponse.model_validate(member).model_dump()}


@router.delete("/{member_id}", status_code=204)
async def delete_member(
    member_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Soft-delete a member. Requires admin or owner. Honours If-Match."""
    service = _get_service(session, auth)
    existing = await service.get(member_id)
    if existing is not None:
        require_if_match(
            request, existing, MemberResponse.model_validate(existing).model_dump(mode="json")
        )
    deleted = await service.delete(member_id)

    if not deleted:
        raise NotFoundError("Member not found")


@router.post("/bulk-delete")
async def bulk_delete_members(
    data: MemberBulkDelete,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Soft-delete multiple members in a single query. Requires admin or owner."""
    service = _get_service(session, auth)
    deleted_count = await service.delete_many(data.ids)
    return {"data": {"deleted": deleted_count}}


@router.get("/{member_id}/federations")
async def list_member_federations(
    member_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """A member's federation memberships (DSB, BDS, …).

    Unpaginated on purpose: a shooter belongs to a handful of federations,
    never to pages of them.
    """
    repo = MemberRepository(session, auth.tenant)
    if await repo.get_by_id(member_id) is None:
        raise NotFoundError("Member not found")
    memberships = await repo.federation_memberships(member_id)
    return {
        "data": [
            FederationMembershipResponse.model_validate(m).model_dump(mode="json")
            for m in memberships
        ]
    }


@router.get("/{member_id}/attendance")
async def list_member_attendance(
    member_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    from_date: date | None = Query(default=None),  # noqa: B008
    to_date: date | None = Query(default=None),  # noqa: B008
) -> dict[str, Any]:
    """One member's attendance history, seen from the board.

    Read-only and deliberately isolated: attendance may inform who was there,
    never how much someone owes. No dues or ranking query joins in here.
    """
    from app.api.v1.attendance import member_records_payload
    from app.services.attendance import AttendanceService

    attendance = AttendanceService(session, auth)
    if await attendance.members.get_by_id(member_id) is None:
        raise NotFoundError("Member not found")
    return await member_records_payload(attendance, member_id, page, per_page, from_date, to_date)
