import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.due import Due, FeeType, MemberFee
from app.models.tenant import Tenant
from app.repositories.due import DueRepository, FeeTypeRepository, MemberFeeRepository
from app.repositories.member import MemberRepository
from app.schemas.due import (
    DuePayRequest,
    DueUpdate,
    FeeTypeCreate,
    FeeTypeUpdate,
    MemberFeeCreate,
    MemberFeeUpdate,
)
from app.services.sepa import SepaCreditor, SepaPayment, build_pain008

PAYMENT_TERM_DAYS = 30


def billing_periods(interval: str, year: int) -> list[tuple[date, date]]:
    """Billing periods of a fee interval within a calendar year."""
    if interval == "yearly":
        return [(date(year, 1, 1), date(year, 12, 31))]
    if interval == "half_yearly":
        return [(date(year, 1, 1), date(year, 6, 30)), (date(year, 7, 1), date(year, 12, 31))]
    if interval == "quarterly":
        return [
            (date(year, q * 3 - 2, 1), date(year, q * 3, calendar.monthrange(year, q * 3)[1]))
            for q in range(1, 5)
        ]
    if interval == "monthly":
        return [
            (date(year, m, 1), date(year, m, calendar.monthrange(year, m)[1])) for m in range(1, 13)
        ]
    return []  # one_time handled separately


class DueService:
    """Business logic for fee types, member fee assignments, and dues."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.fee_types = FeeTypeRepository(session, tenant_id)
        self.member_fees = MemberFeeRepository(session, tenant_id)
        self.dues = DueRepository(session, tenant_id)
        self.members = MemberRepository(session, tenant_id)

    # --- Fee types ---

    async def create_fee_type(self, data: FeeTypeCreate, created_by: uuid.UUID) -> FeeType:
        existing = await self.fee_types.get_by_name(data.name)
        if existing is not None:
            raise ConflictError("A fee type with this name already exists")
        fee_type = FeeType(
            **data.model_dump(),
            tenant_id=self.tenant_id,
            created_by=created_by,
            updated_by=created_by,
        )
        self.session.add(fee_type)
        await self.session.flush()
        await self.session.refresh(fee_type)
        return fee_type

    async def update_fee_type(
        self, fee_type_id: uuid.UUID, data: FeeTypeUpdate, updated_by: uuid.UUID
    ) -> FeeType | None:
        fee_type = await self.fee_types.get_by_id(fee_type_id)
        if fee_type is None:
            return None
        fields = data.model_dump(exclude_unset=True)
        new_name = fields.get("name")
        if new_name and new_name != fee_type.name:
            existing = await self.fee_types.get_by_name(new_name)
            if existing is not None:
                raise ConflictError("A fee type with this name already exists")
        for field, value in fields.items():
            setattr(fee_type, field, value)
        fee_type.updated_by = updated_by
        await self.session.flush()
        await self.session.refresh(fee_type)
        return fee_type

    # --- Member fee assignments ---

    async def assign_fee(self, data: MemberFeeCreate, created_by: uuid.UUID) -> MemberFee:
        member = await self.members.get_by_id(data.member_id)
        if member is None:
            raise NotFoundError("Member not found")
        fee_type = await self.fee_types.get_by_id(data.fee_type_id)
        if fee_type is None:
            raise NotFoundError("Fee type not found")
        if data.valid_to is not None and data.valid_to < data.valid_from:
            raise ValidationError("valid_to must not be before valid_from")
        assignment = MemberFee(
            **data.model_dump(),
            tenant_id=self.tenant_id,
            created_by=created_by,
            updated_by=created_by,
        )
        self.session.add(assignment)
        await self.session.flush()
        await self.session.refresh(assignment)
        return assignment

    async def update_assignment(
        self, assignment_id: uuid.UUID, data: MemberFeeUpdate, updated_by: uuid.UUID
    ) -> MemberFee | None:
        assignment = await self.member_fees.get_by_id(assignment_id)
        if assignment is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(assignment, field, value)
        if assignment.valid_to is not None and assignment.valid_to < assignment.valid_from:
            raise ValidationError("valid_to must not be before valid_from")
        assignment.updated_by = updated_by
        await self.session.flush()
        await self.session.refresh(assignment)
        return assignment

    # --- Assessment run (Sollstellung) ---

    async def generate_dues(self, year: int, created_by: uuid.UUID) -> int:
        """Create open dues for all active fee assignments in the given year.

        Idempotent: existing dues (any status, incl. soft-deleted) for the same
        member/fee type/period are skipped. Returns the number of dues created.
        """
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        assignments = await self.member_fees.get_active_in_period(year_start, year_end)
        existing = await self.dues.get_existing_period_keys(year)

        created = 0
        for assignment, fee_type in assignments:
            for period_start, period_end in self._periods_for(assignment, fee_type, year):
                key = (assignment.member_id, fee_type.id, period_start)
                if key in existing:
                    continue
                existing.add(key)
                self.session.add(
                    Due(
                        tenant_id=self.tenant_id,
                        member_id=assignment.member_id,
                        fee_type_id=fee_type.id,
                        fee_name=fee_type.name,
                        amount=Decimal(fee_type.amount),
                        period_start=period_start,
                        period_end=period_end,
                        due_date=period_start + timedelta(days=PAYMENT_TERM_DAYS),
                        status="open",
                        created_by=created_by,
                        updated_by=created_by,
                    )
                )
                created += 1
        await self.session.flush()
        return created

    def _periods_for(
        self, assignment: MemberFee, fee_type: FeeType, year: int
    ) -> list[tuple[date, date]]:
        if fee_type.interval == "one_time":
            if assignment.valid_from.year != year:
                return []
            return [(assignment.valid_from, assignment.valid_from)]
        periods: list[tuple[date, date]] = []
        for period_start, period_end in billing_periods(fee_type.interval, year):
            if assignment.valid_from > period_end:
                continue
            if assignment.valid_to is not None and assignment.valid_to < period_start:
                continue
            periods.append((period_start, period_end))
        return periods

    # --- SEPA export ---

    async def build_sepa_export(
        self,
        *,
        year: int | None = None,
        collection_date: date | None = None,
    ) -> tuple[str, int]:
        """Build a pain.008 XML for all open dues with complete SEPA data.

        Returns (xml, transaction_count). Raises ValidationError if the club's
        creditor data is incomplete or no eligible dues exist.
        """
        stmt = select(Tenant).where(Tenant.id == self.tenant_id)
        result = await self.session.execute(stmt)
        tenant = result.scalar_one()

        if not tenant.iban or not tenant.sepa_creditor_id:
            raise ValidationError("Club SEPA creditor data is incomplete (IBAN, creditor ID)")

        rows = await self.dues.get_open_for_sepa(year=year)
        if not rows:
            raise ValidationError("No open dues with complete SEPA data found")

        payments = [
            SepaPayment(
                end_to_end_id=due.id.hex,
                amount=Decimal(due.amount),
                debtor_name=member.account_holder or f"{member.first_name} {member.last_name}",
                debtor_iban=member.iban or "",
                debtor_bic=member.bic,
                mandate_reference=member.sepa_mandate_reference or "",
                mandate_date=member.sepa_mandate_date or date.today(),
                remittance_info=(
                    f"{due.fee_name} {due.period_start.year} - Mitglied {member.member_number}"
                ),
            )
            for due, member in rows
        ]
        creditor = SepaCreditor(
            name=tenant.name,
            iban=tenant.iban,
            bic=tenant.bic,
            creditor_id=tenant.sepa_creditor_id,
        )
        xml = build_pain008(
            creditor,
            payments,
            collection_date=collection_date or date.today() + timedelta(days=5),
        )
        return xml, len(payments)

    # --- Payments / status ---

    async def pay_due(
        self, due_id: uuid.UUID, data: DuePayRequest, updated_by: uuid.UUID
    ) -> Due | None:
        due = await self.dues.get_by_id(due_id)
        if due is None:
            return None
        if due.status != "open":
            raise ConflictError(f"Due is not open (status: {due.status})")
        due.status = "paid"
        due.paid_at = data.paid_at or date.today()
        due.payment_method = data.payment_method
        if data.note is not None:
            due.note = data.note
        due.updated_by = updated_by
        await self.session.flush()
        await self.session.refresh(due)
        return due

    async def cancel_due(self, due_id: uuid.UUID, updated_by: uuid.UUID) -> Due | None:
        due = await self.dues.get_by_id(due_id)
        if due is None:
            return None
        if due.status == "paid":
            raise ConflictError("Paid dues cannot be cancelled")
        due.status = "cancelled"
        due.updated_by = updated_by
        await self.session.flush()
        await self.session.refresh(due)
        return due

    async def reopen_due(self, due_id: uuid.UUID, updated_by: uuid.UUID) -> Due | None:
        due = await self.dues.get_by_id(due_id)
        if due is None:
            return None
        due.status = "open"
        due.paid_at = None
        due.payment_method = None
        due.updated_by = updated_by
        await self.session.flush()
        await self.session.refresh(due)
        return due

    async def update_due(
        self, due_id: uuid.UUID, data: DueUpdate, updated_by: uuid.UUID
    ) -> Due | None:
        due = await self.dues.get_by_id(due_id)
        if due is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(due, field, value)
        due.updated_by = updated_by
        await self.session.flush()
        await self.session.refresh(due)
        return due
