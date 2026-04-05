import math
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.repositories.member import MemberRepository
from app.schemas.member import (
    MemberBulkDelete,
    MemberCreate,
    MemberResponse,
    MemberUpdate,
)
from app.services.member import MemberService

router = APIRouter()


def _get_service(session: AsyncSession, auth: AuthContext) -> MemberService:
    repo = MemberRepository(session, auth.tenant_id)
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
    sort_by: str = Query(default="last_name"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
) -> dict:
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


@router.get("/{member_id}")
async def get_member(
    member_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """Get a single member."""
    service = _get_service(session, auth)
    member = await service.get(member_id)

    if member is None:
        raise NotFoundError("Member not found")

    return {"data": MemberResponse.model_validate(member).model_dump()}


@router.post("", status_code=201)
async def create_member(
    data: MemberCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """Create a new member. Member number is auto-generated."""
    service = _get_service(session, auth)
    member = await service.create(data, created_by=auth.user_id)

    return {"data": MemberResponse.model_validate(member).model_dump()}


@router.patch("/{member_id}")
async def update_member(
    member_id: uuid.UUID,
    data: MemberUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """Update a member."""
    service = _get_service(session, auth)
    member = await service.update(member_id, data, updated_by=auth.user_id)

    if member is None:
        raise NotFoundError("Member not found")

    return {"data": MemberResponse.model_validate(member).model_dump()}


@router.delete("/{member_id}", status_code=204)
async def delete_member(
    member_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Soft-delete a member. Requires admin or owner."""
    service = _get_service(session, auth)
    deleted = await service.delete(member_id)

    if not deleted:
        raise NotFoundError("Member not found")


@router.post("/bulk-delete")
async def bulk_delete_members(
    data: MemberBulkDelete,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict:
    """Soft-delete multiple members in a single query. Requires admin or owner."""
    service = _get_service(session, auth)
    deleted_count = await service.delete_many(data.ids)
    return {"data": {"deleted": deleted_count}}
