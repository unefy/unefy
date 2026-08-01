import math
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.schemas.due import (
    DueGenerateRequest,
    DuePayRequest,
    DueResponse,
    DueSummaryResponse,
    DueUpdate,
    FeeTypeCreate,
    FeeTypeResponse,
    FeeTypeUpdate,
    MemberFeeCreate,
    MemberFeeResponse,
    MemberFeeUpdate,
)
from app.services.due import DueService

router = APIRouter()


def _get_service(session: AsyncSession, auth: AuthContext) -> DueService:
    return DueService(session, auth.tenant)


# --- Fee types ---


@router.get("/fee-types")
async def list_fee_types(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    include_inactive: bool = Query(default=False),
) -> dict[str, Any]:
    """List fee types."""
    service = _get_service(session, auth)
    fee_types = await service.fee_types.get_all(include_inactive=include_inactive)
    return {"data": [FeeTypeResponse.model_validate(f).model_dump(mode="json") for f in fee_types]}


@router.post("/fee-types", status_code=201)
async def create_fee_type(
    data: FeeTypeCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Create a fee type."""
    service = _get_service(session, auth)
    fee_type = await service.create_fee_type(data, created_by=auth.user_id)
    return {"data": FeeTypeResponse.model_validate(fee_type).model_dump(mode="json")}


@router.patch("/fee-types/{fee_type_id}")
async def update_fee_type(
    fee_type_id: uuid.UUID,
    data: FeeTypeUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Update a fee type."""
    service = _get_service(session, auth)
    fee_type = await service.update_fee_type(fee_type_id, data, updated_by=auth.user_id)
    if fee_type is None:
        raise NotFoundError("Fee type not found")
    return {"data": FeeTypeResponse.model_validate(fee_type).model_dump(mode="json")}


@router.delete("/fee-types/{fee_type_id}", status_code=204)
async def delete_fee_type(
    fee_type_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Soft-delete a fee type."""
    service = _get_service(session, auth)
    deleted = await service.fee_types.soft_delete(fee_type_id)
    if not deleted:
        raise NotFoundError("Fee type not found")


# --- Member fee assignments ---


@router.get("/assignments")
async def list_assignments(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    member_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    fee_type_id: uuid.UUID | None = Query(default=None),  # noqa: B008
) -> dict[str, Any]:
    """List member fee assignments, optionally filtered."""
    service = _get_service(session, auth)
    assignments = await service.member_fees.get_all(
        member_id=member_id, fee_type_id=fee_type_id, limit=500
    )
    return {
        "data": [MemberFeeResponse.model_validate(a).model_dump(mode="json") for a in assignments]
    }


@router.post("/assignments", status_code=201)
async def create_assignment(
    data: MemberFeeCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Assign a fee type to a member."""
    service = _get_service(session, auth)
    assignment = await service.assign_fee(data, created_by=auth.user_id)
    return {"data": MemberFeeResponse.model_validate(assignment).model_dump(mode="json")}


@router.patch("/assignments/{assignment_id}")
async def update_assignment(
    assignment_id: uuid.UUID,
    data: MemberFeeUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Update a fee assignment."""
    service = _get_service(session, auth)
    assignment = await service.update_assignment(assignment_id, data, updated_by=auth.user_id)
    if assignment is None:
        raise NotFoundError("Assignment not found")
    return {"data": MemberFeeResponse.model_validate(assignment).model_dump(mode="json")}


@router.delete("/assignments/{assignment_id}", status_code=204)
async def delete_assignment(
    assignment_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Remove a fee assignment."""
    service = _get_service(session, auth)
    deleted = await service.member_fees.soft_delete(assignment_id)
    if not deleted:
        raise NotFoundError("Assignment not found")


# --- Dues ---


@router.get("/summary")
async def dues_summary(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> dict[str, Any]:
    """Open/paid totals, optionally per year."""
    service = _get_service(session, auth)
    summary = await service.dues.summary(year=year)
    return {"data": DueSummaryResponse.model_validate(summary).model_dump(mode="json")}


@router.get("/sepa-export")
async def sepa_export(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    year: int | None = Query(default=None, ge=2000, le=2100),
    collection_date: date | None = Query(default=None),  # noqa: B008
) -> Response:
    """Download a SEPA pain.008 direct debit XML for all open dues."""
    service = _get_service(session, auth)
    xml, count = await service.build_sepa_export(year=year, collection_date=collection_date)
    filename = f"sepa-lastschrift-{year or date.today().year}.xml"
    return Response(
        content=xml,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Transaction-Count": str(count),
        },
    )


@router.get("")
async def list_dues(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, pattern="^(open|paid|cancelled)$"),
    member_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> dict[str, Any]:
    """List dues with pagination and filters."""
    service = _get_service(session, auth)
    offset = (page - 1) * per_page
    rows = await service.dues.get_all_with_member(
        offset=offset, limit=per_page, status=status, member_id=member_id, year=year
    )
    total = await service.dues.count(status=status, member_id=member_id, year=year)
    return {
        "data": [
            DueResponse.model_validate(due).model_dump(mode="json")
            | {"member_name": f"{first} {last}"}
            for due, first, last in rows
        ],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total > 0 else 1,
        },
    }


@router.post("/generate")
async def generate_dues(
    data: DueGenerateRequest,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Run the assessment for a year. Idempotent — existing dues are skipped."""
    service = _get_service(session, auth)
    created = await service.generate_dues(data.year, created_by=auth.user_id)
    return {"data": {"created": created}}


@router.patch("/{due_id}")
async def update_due(
    due_id: uuid.UUID,
    data: DueUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Update note or due date of a due."""
    service = _get_service(session, auth)
    due = await service.update_due(due_id, data, updated_by=auth.user_id)
    if due is None:
        raise NotFoundError("Due not found")
    return {"data": DueResponse.model_validate(due).model_dump(mode="json")}


@router.post("/{due_id}/pay")
async def pay_due(
    due_id: uuid.UUID,
    data: DuePayRequest,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Mark an open due as paid."""
    service = _get_service(session, auth)
    due = await service.pay_due(due_id, data, updated_by=auth.user_id)
    if due is None:
        raise NotFoundError("Due not found")
    return {"data": DueResponse.model_validate(due).model_dump(mode="json")}


@router.post("/{due_id}/cancel")
async def cancel_due(
    due_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Cancel an open due."""
    service = _get_service(session, auth)
    due = await service.cancel_due(due_id, updated_by=auth.user_id)
    if due is None:
        raise NotFoundError("Due not found")
    return {"data": DueResponse.model_validate(due).model_dump(mode="json")}


@router.post("/{due_id}/reopen")
async def reopen_due(
    due_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Reopen a paid or cancelled due."""
    service = _get_service(session, auth)
    due = await service.reopen_due(due_id, updated_by=auth.user_id)
    if due is None:
        raise NotFoundError("Due not found")
    return {"data": DueResponse.model_validate(due).model_dump(mode="json")}
