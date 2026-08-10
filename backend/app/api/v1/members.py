import json
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
from app.schemas.consent import ConsentEntry, ConsentRecord
from app.schemas.function import MemberFunctionCreate, MemberFunctionUpdate
from app.schemas.member import (
    FederationMembershipResponse,
    MemberBulkDelete,
    MemberCreate,
    MemberDirectoryEntry,
    MemberResponse,
    MemberUpdate,
)
from app.services.consent import ConsentService
from app.services.data_export import DataExportService
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


@router.get("/me/functions")
async def list_own_functions(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """The caller's own terms of office.

    Declared before `/{member_id}/functions`, which would otherwise swallow
    "me" as a malformed UUID. Empty for an account with no member record —
    an unlinked treasurer holds no office, which is a state and not an error.
    """
    from app.services.function import FunctionService

    member_repo = MemberRepository(session, auth.tenant)
    member = await member_repo.get_by_user_id(auth.user_id)
    if member is None:
        return {"data": []}

    service = FunctionService(session, auth.tenant)
    assignments = await service.list_member_functions(member.id)
    return {"data": [a.model_dump(mode="json") for a in assignments]}


@router.get("/{member_id}/functions")
async def list_member_functions(
    member_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """A member's terms of office, newest first, history included."""
    from app.services.function import FunctionService

    service = FunctionService(session, auth.tenant)
    assignments = await service.list_member_functions(member_id)
    return {"data": [a.model_dump(mode="json") for a in assignments]}


@router.post("/{member_id}/functions", status_code=201)
async def assign_member_function(
    member_id: uuid.UUID,
    data: MemberFunctionCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Start a term of office for a member."""
    from app.services.function import FunctionService

    service = FunctionService(session, auth.tenant)
    assignment = await service.assign(member_id, data, created_by=auth.user_id)
    return {"data": assignment.model_dump(mode="json")}


@router.patch("/{member_id}/functions/{assignment_id}")
async def update_member_function(
    member_id: uuid.UUID,
    assignment_id: uuid.UUID,
    data: MemberFunctionUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Adjust a term — typically setting `valid_to` to end it."""
    from app.services.function import FunctionService

    service = FunctionService(session, auth.tenant)
    assignment = await service.update_assignment(
        member_id, assignment_id, data, updated_by=auth.user_id
    )
    return {"data": assignment.model_dump(mode="json")}


@router.delete("/{member_id}/functions/{assignment_id}", status_code=204)
async def delete_member_function(
    member_id: uuid.UUID,
    assignment_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Remove a term entirely — for typos only; ending a term sets `valid_to`."""
    from app.services.function import FunctionService

    service = FunctionService(session, auth.tenant)
    await service.delete_assignment(member_id, assignment_id)


# --- Consents (GDPR) ---
#
# `/me/...` before `/{member_id}/...` throughout this file: the parameterised
# route parses its segment as a UUID and would reject "me" before the
# self-service handler ever ran.


async def _own_member_id(session: AsyncSession, auth: AuthContext) -> uuid.UUID:
    member = await MemberRepository(session, auth.tenant).get_by_user_id(auth.user_id)
    if member is None:
        raise NotFoundError("No member record is linked to this account")
    return member.id


@router.get("/me/consents")
async def get_own_consents(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """What the caller has allowed, and how that came about.

    The history is shown to the member as well as the board. Somebody who
    asks what a club holds about them is entitled to see when they were asked
    and what they answered — that is the record's purpose, not the club's.
    """
    member_id = await _own_member_id(session, auth)
    overview = await ConsentService(session, auth.tenant).overview(member_id)
    return {"data": overview.model_dump(mode="json")}


@router.post("/me/consents", status_code=201)
async def record_own_consent(
    data: ConsentRecord,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Give or withdraw a consent. Same call for both directions.

    A withdrawal that is harder to perform than the consent was is not a valid
    withdrawal, and two endpoints would invite exactly that asymmetry.

    `recorded_at` from the body is ignored here: a member answering in their
    own account answers now, and letting the client choose the timestamp would
    make the ledger a place to write history rather than record it.
    """
    member_id = await _own_member_id(session, auth)
    service = ConsentService(session, auth.tenant)
    entry = await service.record(
        member_id,
        ConsentRecord(kind=data.kind, granted=data.granted, note=data.note),
        source="self",
        recorded_by=auth.user_id,
    )
    return {"data": ConsentEntry.model_validate(entry).model_dump(mode="json")}


@router.get("/{member_id}/consents")
async def get_member_consents(
    member_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """One member's consents, current state and full trail."""
    if await MemberRepository(session, auth.tenant).get_by_id(member_id) is None:
        raise NotFoundError("Member not found")
    overview = await ConsentService(session, auth.tenant).overview(member_id)
    return {"data": overview.model_dump(mode="json")}


@router.post("/{member_id}/consents", status_code=201)
async def record_member_consent(
    member_id: uuid.UUID,
    data: ConsentRecord,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Record an answer the club received outside the system.

    Here `recorded_at` is honoured: a paper form that arrives three weeks late
    was signed on the day it was signed, and backdating it is the accurate
    entry rather than a convenience.
    """
    if await MemberRepository(session, auth.tenant).get_by_id(member_id) is None:
        raise NotFoundError("Member not found")
    entry = await ConsentService(session, auth.tenant).record(
        member_id, data, source="board", recorded_by=auth.user_id
    )
    return {"data": ConsentEntry.model_validate(entry).model_dump(mode="json")}


# --- Data export (Art. 15 / Art. 20 GDPR) ---


@router.get("/me/export")
async def export_own_data(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> Response:
    """Everything the club holds about the caller, as a JSON download.

    Self-service and unconditional: Art. 15 is the member's right, and making
    them ask the board for it would put the club between a person and their
    own data for no reason the law recognises.

    Returned as a file rather than in the usual envelope — the recipient wants
    something they can keep, forward, or hand to an authority, not a response
    body they would have to copy out of a browser tab.
    """
    member_id = await _own_member_id(session, auth)
    payload = await DataExportService(session, auth.tenant).export_member(member_id)
    return _export_response(payload, member_id)


@router.get("/{member_id}/export")
async def export_member_data(
    member_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> Response:
    """The same bundle, for a board answering a request that arrived on paper.

    Not every member has an account, and a right that only works for people
    who signed in is not the right the law describes.
    """
    payload = await DataExportService(session, auth.tenant).export_member(member_id)
    return _export_response(payload, member_id)


def _export_response(payload: dict[str, Any], member_id: uuid.UUID) -> Response:
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            # The member number would be friendlier, but it is also the one
            # thing on this file that identifies a person to anyone who sees
            # the filename in a downloads folder.
            "Content-Disposition": f'attachment; filename="unefy-export-{member_id}.json"',
            # A copy of personal data has no business in any cache.
            "Cache-Control": "no-store",
        },
    )
