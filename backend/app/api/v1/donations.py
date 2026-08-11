"""Donation receipts — the prescribed form."""

import uuid
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.models.tenant import Tenant
from app.schemas.donation import (
    ReadinessResponse,
    ReceiptCreate,
    ReceiptResponse,
    RevokeRequest,
)
from app.services.donation import DonationService
from app.services.donation_pdf import DonationDocument, build_donation_pdf

router = APIRouter()


@router.get("/readiness")
async def check_readiness(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Whether the club can issue receipts, and what is missing if not.

    Asked before the form is shown rather than after it is submitted: telling
    somebody their tax number is missing once they have typed a donor's
    address is a poor way to run a settings check.
    """
    tenant = await session.get(Tenant, auth.tenant)
    missing = (
        [
            field
            for field, value in (
                ("nonprofit_purposes", tenant.nonprofit_purposes),
                ("tax_exemption_kind", tenant.tax_exemption_kind),
                ("tax_exemption_date", tenant.tax_exemption_date),
                ("tax_office", tenant.tax_office),
                ("tax_number", tenant.tax_number),
            )
            if not value
        ]
        if tenant
        else ["club"]
    )
    if (
        tenant
        and tenant.tax_exemption_kind == "freistellungsbescheid"
        and tenant.tax_exemption_period is None
    ):
        missing.append("tax_exemption_period")

    return {
        "data": ReadinessResponse(
            ready=not missing,
            missing=missing,
            membership_fees_deductible=bool(tenant and tenant.membership_fees_deductible),
        ).model_dump()
    }


@router.get("")
async def list_receipts(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    member_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    year: int | None = Query(default=None, ge=1900, le=2200),
) -> dict[str, Any]:
    receipts = await DonationService(session, auth.tenant).list(member_id=member_id, year=year)
    return {"data": [ReceiptResponse.model_validate(r).model_dump(mode="json") for r in receipts]}


@router.post("", status_code=201)
async def issue_receipt(
    data: ReceiptCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Issue a receipt for one donation.

    Refuses on incomplete tax data, and refuses a membership fee unless the
    club has said its recognised purposes allow certifying one.
    """
    receipt = await DonationService(session, auth.tenant).issue(data, issued_by=auth.user_id)
    return {"data": ReceiptResponse.model_validate(receipt).model_dump(mode="json")}


@router.post("/{receipt_id}/revoke")
async def revoke_receipt(
    receipt_id: uuid.UUID,
    data: RevokeRequest,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    receipt = await DonationService(session, auth.tenant).revoke(
        receipt_id, reason=data.reason, revoked_by=auth.user_id
    )
    return {"data": ReceiptResponse.model_validate(receipt).model_dump(mode="json")}


@router.get("/{receipt_id}/pdf")
async def download_receipt(
    receipt_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> Response:
    """The receipt as it was issued, re-rendered from the frozen fields."""
    service = DonationService(session, auth.tenant)
    receipt = await service.get(receipt_id)
    tenant = await session.get(Tenant, auth.tenant)

    settings = get_settings()
    zone = ZoneInfo(tenant.timezone if tenant else "Europe/Berlin")
    document = DonationDocument(
        club_name=receipt.club_name,
        club_address=receipt.club_address,
        donor_name=receipt.donor_name,
        donor_address=receipt.donor_address,
        amount=receipt.amount,
        received_on=receipt.received_on,
        kind=receipt.kind,
        is_expense_waiver=receipt.is_expense_waiver,
        exemption_kind=receipt.exemption_kind,
        exemption_date=receipt.exemption_date,
        exemption_period=receipt.exemption_period,
        tax_office=receipt.tax_office,
        tax_number=receipt.tax_number,
        purposes=receipt.purposes,
        # The club's day, so the printed date matches the check page.
        issued_on=receipt.issued_at.astimezone(zone).date(),
        verification_code=receipt.verification_code,
        verification_url=(f"{settings.WEB_APP_URL.rstrip('/')}/verify/{receipt.verification_code}"),
        revoked=receipt.revoked_at is not None,
    )

    return Response(
        content=build_donation_pdf(document),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="zuwendungsbestaetigung-{receipt.received_on.year}-'
                f'{receipt.verification_code}.pdf"'
            ),
            "Cache-Control": "no-store",
        },
    )
