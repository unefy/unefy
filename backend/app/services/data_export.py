"""Everything the club holds about one person, in one file.

Art. 15 DSGVO gives a member the right to a copy of their data; Art. 20 wants
it in a structured, commonly used, machine-readable form. JSON satisfies both
and stays readable to a human who opens it, which a CSV bundle would not.

Assembled from the same tables the member's own pages already read. That is
deliberate: an export that goes through a second, parallel set of queries
drifts from what the app shows, and then nobody can say which one is the
truth. If something is missing here it is missing because the club does not
hold it, not because the export forgot to ask.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.attendance import AttendanceRecord
from app.models.consent import MemberConsent
from app.models.due import Due, FeeType, MemberFee
from app.models.event import Event, EventRegistration
from app.models.function import Function, MemberFunction
from app.models.member import Member, MemberFederationMembership
from app.models.tenant import Tenant


def _plain(value: Any) -> Any:
    """JSON-safe scalars. Money stays a string — a float would round it."""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _row(obj: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: _plain(getattr(obj, field)) for field in fields}


class DataExportService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def export_member(self, member_id: uuid.UUID) -> dict[str, Any]:
        member = (
            await self.session.execute(
                select(Member)
                .where(Member.tenant_id == self.tenant_id)
                .where(Member.id == member_id)
            )
        ).scalar_one_or_none()
        if member is None:
            raise NotFoundError("Member not found")

        tenant = (
            await self.session.execute(select(Tenant).where(Tenant.id == self.tenant_id))
        ).scalar_one()

        return {
            # Who produced this and when, so a printed copy can be placed in
            # time without the recipient having to take our word for it.
            "export": {
                "generated_at": datetime.now(UTC).isoformat(),
                "controller": tenant.name,
                "subject": f"{member.first_name} {member.last_name}",
                "note": (
                    "Personal data held about this member, exported under "
                    "Art. 15 GDPR. Financial and attendance records are kept "
                    "for the retention periods the club is required to observe."
                ),
            },
            "member": _row(
                member,
                (
                    "id",
                    "member_number",
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "mobile",
                    "birthday",
                    "gender",
                    "street",
                    "zip_code",
                    "city",
                    "state",
                    "country",
                    "joined_at",
                    "left_at",
                    "status",
                    "category",
                    "notes",
                    "iban",
                    "bic",
                    "account_holder",
                    "sepa_mandate_reference",
                    "sepa_mandate_date",
                    "created_at",
                    "updated_at",
                ),
            ),
            "consents": await self._consents(member_id),
            "federations": await self._federations(member_id),
            "functions": await self._functions(member_id),
            "fees": await self._fees(member_id),
            "dues": await self._dues(member_id),
            "attendance": await self._attendance(member_id),
            "event_registrations": await self._registrations(member_id),
        }

    async def _consents(self, member_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            (
                await self.session.execute(
                    select(MemberConsent)
                    .where(MemberConsent.tenant_id == self.tenant_id)
                    .where(MemberConsent.member_id == member_id)
                    .order_by(MemberConsent.recorded_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return [_row(r, ("kind", "granted", "recorded_at", "source", "note")) for r in rows]

    async def _federations(self, member_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            (
                await self.session.execute(
                    select(MemberFederationMembership)
                    .where(MemberFederationMembership.tenant_id == self.tenant_id)
                    .where(MemberFederationMembership.member_id == member_id)
                    .where(MemberFederationMembership.deleted_at.is_(None))
                )
            )
            .scalars()
            .all()
        )
        return [
            _row(r, ("federation", "federation_number", "joined_at", "left_at", "notes"))
            for r in rows
        ]

    async def _functions(self, member_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(MemberFunction, Function.name)
                .join(Function, Function.id == MemberFunction.function_id)
                .where(MemberFunction.tenant_id == self.tenant_id)
                .where(MemberFunction.member_id == member_id)
                .order_by(MemberFunction.valid_from.desc())
            )
        ).all()
        return [
            {"function": name, **_row(f, ("valid_from", "valid_to", "note"))} for f, name in rows
        ]

    async def _fees(self, member_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(MemberFee, FeeType.name, FeeType.amount, FeeType.interval)
                .join(FeeType, FeeType.id == MemberFee.fee_type_id)
                .where(MemberFee.tenant_id == self.tenant_id)
                .where(MemberFee.member_id == member_id)
                .where(MemberFee.deleted_at.is_(None))
                .order_by(MemberFee.valid_from.desc())
            )
        ).all()
        return [
            {
                "fee_type": name,
                "amount": _plain(amount),
                "interval": interval,
                **_row(f, ("valid_from", "valid_to", "note")),
            }
            for f, name, amount, interval in rows
        ]

    async def _dues(self, member_id: uuid.UUID) -> list[dict[str, Any]]:
        """Assessed dues and how each was settled.

        Payments are not a separate table here — a due carries its own
        `paid_at` and `payment_method` — so there is nothing to join.
        """
        rows = (
            (
                await self.session.execute(
                    select(Due)
                    .where(Due.tenant_id == self.tenant_id)
                    .where(Due.member_id == member_id)
                    .where(Due.deleted_at.is_(None))
                    .order_by(Due.period_start.desc())
                )
            )
            .scalars()
            .all()
        )
        return [
            _row(
                due,
                (
                    "fee_name",
                    "amount",
                    "period_start",
                    "period_end",
                    "due_date",
                    "status",
                    "paid_at",
                    "payment_method",
                    "note",
                ),
            )
            for due in rows
        ]

    async def _attendance(self, member_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            (
                await self.session.execute(
                    select(AttendanceRecord)
                    .where(AttendanceRecord.tenant_id == self.tenant_id)
                    .where(AttendanceRecord.member_id == member_id)
                    .where(AttendanceRecord.deleted_at.is_(None))
                    .order_by(AttendanceRecord.occurred_on.desc())
                )
            )
            .scalars()
            .all()
        )
        return [
            _row(
                r,
                (
                    "occurred_on",
                    "origin",
                    "external_location",
                    "method",
                    "assurance",
                    "checked_in_at",
                    "checked_out_at",
                    "note",
                ),
            )
            for r in rows
        ]

    async def _registrations(self, member_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                select(EventRegistration, Event.title, Event.starts_at)
                .join(Event, Event.id == EventRegistration.event_id)
                .where(EventRegistration.tenant_id == self.tenant_id)
                .where(EventRegistration.member_id == member_id)
                .where(EventRegistration.deleted_at.is_(None))
                .order_by(Event.starts_at.desc())
            )
        ).all()
        return [
            {
                "event": title,
                "starts_at": _plain(starts_at),
                **_row(r, ("status", "created_at")),
            }
            for r, title, starts_at in rows
        ]
