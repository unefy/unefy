"""Donation receipts: the prescribed form, and the checks that keep it valid.

Two refusals carry this module, and both exist because the alternative is a
piece of paper that costs somebody money.

**Membership fees to a sports club are not deductible** (§ 10b Abs. 1 Satz 8
EStG together with § 52 Abs. 2 Nr. 21 AO). A club that certifies them anyway
hands its members a receipt the tax office will reject and takes on liability
for the tax it caused to be avoided (§ 10b Abs. 4 EStG). So the club has to
say explicitly that its recognised purposes allow it, and the default is no.

**Incomplete tax data blocks issuing.** The form names the notice that
recognises the club, its date and the office that issued it. Leaving those
blank produces a receipt that looks official and asserts nothing, which is
worse than no receipt at all.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.donation import DonationReceipt
from app.models.member import Member
from app.models.tenant import Tenant
from app.schemas.donation import ReceiptCreate

logger = structlog.get_logger()

#: Same alphabet and length as the other verifiable documents — a member may
#: hold several and should not have to learn two ways of reading a code.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 11


class DonationService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def issue(self, data: ReceiptCreate, *, issued_by: uuid.UUID) -> DonationReceipt:
        tenant = (
            await self.session.execute(select(Tenant).where(Tenant.id == self.tenant_id))
        ).scalar_one()

        self._require_complete_tax_data(tenant)
        self._require_certifiable(tenant, data.kind)

        member, donor_name, donor_address = await self._resolve_donor(data)

        today = datetime.now(ZoneInfo(tenant.timezone)).date()
        if data.received_on > today:
            # A receipt for money that has not arrived is not a receipt.
            raise ValidationError("The donation date is in the future")

        issued_at = datetime.now(UTC)
        receipt = DonationReceipt(
            tenant_id=self.tenant_id,
            member_id=member.id if member else None,
            donor_name=donor_name,
            donor_address=donor_address,
            amount=data.amount,
            received_on=data.received_on,
            kind=data.kind,
            is_expense_waiver=data.is_expense_waiver,
            # Copied in, not referenced: the club's own data changes and a
            # receipt from 2024 has to keep saying what was true in 2024.
            club_name=tenant.name,
            club_address=_one_line(tenant.street, tenant.zip_code, tenant.city),
            exemption_kind=tenant.tax_exemption_kind or "",
            exemption_date=tenant.tax_exemption_date or today,
            exemption_period=tenant.tax_exemption_period,
            tax_office=tenant.tax_office or "",
            tax_number=tenant.tax_number or "",
            purposes=tenant.nonprofit_purposes or "",
            issued_at=issued_at,
            issued_by_user_id=issued_by,
            verification_code=self._verification_code(),
            content_hash="",
            created_by=issued_by,
            updated_by=issued_by,
        )
        receipt.content_hash = _content_hash(receipt)

        self.session.add(receipt)
        await self.session.flush()

        logger.info(
            "donation_receipt_issued",
            tenant_id=str(self.tenant_id),
            kind=data.kind,
        )
        return receipt

    async def revoke(
        self, receipt_id: uuid.UUID, *, reason: str, revoked_by: uuid.UUID
    ) -> DonationReceipt:
        """Withdraw a receipt. The row and its content stay.

        The donor still holds the paper and the tax office may already have
        seen it, so a correction that quietly overwrote the old figures would
        leave nothing to explain the difference with.
        """
        receipt = await self.get(receipt_id)
        if receipt.revoked_at is not None:
            raise ConflictError("This receipt is already revoked")

        receipt.revoked_at = datetime.now(UTC)
        receipt.revoked_by_user_id = revoked_by
        receipt.revoke_reason = reason
        receipt.updated_by = revoked_by
        await self.session.flush()
        return receipt

    async def get(self, receipt_id: uuid.UUID) -> DonationReceipt:
        receipt = (
            await self.session.execute(
                select(DonationReceipt)
                .where(DonationReceipt.tenant_id == self.tenant_id)
                .where(DonationReceipt.id == receipt_id)
            )
        ).scalar_one_or_none()
        if receipt is None:
            raise NotFoundError("Receipt not found")
        return receipt

    async def list(
        self, *, member_id: uuid.UUID | None = None, year: int | None = None
    ) -> list[DonationReceipt]:
        query = (
            select(DonationReceipt)
            .where(DonationReceipt.tenant_id == self.tenant_id)
            .order_by(DonationReceipt.received_on.desc())
        )
        if member_id is not None:
            query = query.where(DonationReceipt.member_id == member_id)
        if year is not None:
            query = query.where(
                DonationReceipt.received_on >= date(year, 1, 1),
                DonationReceipt.received_on <= date(year, 12, 31),
            )
        return list((await self.session.execute(query)).scalars().all())

    # --- The checks ---

    def _require_complete_tax_data(self, tenant: Tenant) -> None:
        missing = [
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
        if missing:
            raise ValidationError(
                "The club's tax exemption data is incomplete",
                details=[{"field": field, "message": "required"} for field in missing],
            )
        if (
            tenant.tax_exemption_kind == "freistellungsbescheid"
            and tenant.tax_exemption_period is None
        ):
            raise ValidationError(
                "The club's tax exemption data is incomplete",
                details=[{"field": "tax_exemption_period", "message": "required"}],
            )

    def _require_certifiable(self, tenant: Tenant, kind: str) -> None:
        if kind == "mitgliedsbeitrag" and not tenant.membership_fees_deductible:
            raise ValidationError(
                "Membership fees cannot be certified for this club",
                details=[
                    {
                        "field": "kind",
                        # Named so the club can look it up rather than take our
                        # word for it.
                        "message": "membership_fees_not_deductible",
                    }
                ],
            )

    async def _resolve_donor(self, data: ReceiptCreate) -> tuple[Member | None, str, str | None]:
        """A donor need not be a member, but a named member must exist here.

        When a member is given, their name and address are copied from the
        record rather than typed again: a receipt whose donor name differs
        from the register by a typo is a receipt somebody has to explain.
        """
        if data.member_id is None:
            if not data.donor_name:
                raise ValidationError("A donor name is required")
            return None, data.donor_name.strip(), (data.donor_address or "").strip() or None

        member = (
            await self.session.execute(
                select(Member)
                .where(Member.tenant_id == self.tenant_id)
                .where(Member.id == data.member_id)
                .where(Member.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if member is None:
            raise NotFoundError("Member not found")

        return (
            member,
            f"{member.first_name} {member.last_name}".strip(),
            _one_line(member.street, member.zip_code, member.city),
        )

    def _verification_code(self) -> str:
        return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


def _one_line(street: str | None, zip_code: str | None, city: str | None) -> str | None:
    town = " ".join(part for part in (zip_code, city) if part).strip()
    parts = [part for part in (street, town) if part and part.strip()]
    return ", ".join(parts) or None


def _content_hash(receipt: DonationReceipt) -> str:
    """SHA-256 over everything the receipt asserts.

    Every field the form prints goes in. A hash over a subset would let the
    part it skipped be changed without trace, which defeats the point.
    """
    canonical = "|".join(
        str(value)
        for value in (
            receipt.donor_name,
            receipt.donor_address,
            receipt.amount,
            receipt.received_on,
            receipt.kind,
            receipt.is_expense_waiver,
            receipt.club_name,
            receipt.exemption_kind,
            receipt.exemption_date,
            receipt.exemption_period,
            receipt.tax_office,
            receipt.tax_number,
            receipt.purposes,
            receipt.issued_at.isoformat(),
        )
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


async def receipt_by_verification_code(
    session: AsyncSession, code: str
) -> tuple[DonationReceipt, str] | None:
    """Look up a receipt for the public check page, across all clubs.

    Returns the receipt and an abbreviated donor name. Whoever finds a lost
    receipt learns that it is genuine, not who gave what — the amount stays
    off the page for the same reason.
    """
    receipt = (
        await session.execute(
            select(DonationReceipt).where(DonationReceipt.verification_code == code)
        )
    ).scalar_one_or_none()
    if receipt is None:
        return None

    parts = receipt.donor_name.split()
    short = f"{parts[0][:1]}. {' '.join(parts[1:])}" if len(parts) > 1 else receipt.donor_name
    return receipt, short
