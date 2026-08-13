"""Annual figures for the report a club owes its members.

Read-only aggregation over tables that already exist — nothing here writes,
and nothing here is stored. A Rechenschaftsbericht is recomputed every time it
is asked for, because a cached figure that disagrees with the ledger is worse
than a slow page.

**The reporting period is the calendar year.** No club in the data model
carries a different business year yet; when one does, this is the file that
learns about it, and the year boundaries below are the only place that needs to
know.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord, AttendanceSession
from app.models.due import Due
from app.models.incoming_invoice import IncomingInvoice
from app.models.member import Member
from app.models.tenant import Tenant

#: Age bands at the end of the reporting year. Chosen for what federations ask
#: for rather than for even spacing: the youth figure is the one a club has to
#: report, and everything above it is one number to most of them.
AGE_BANDS: tuple[tuple[str, int | None, int | None], ...] = (
    ("under_18", None, 17),
    ("18_to_26", 18, 26),
    ("27_to_40", 27, 40),
    ("41_to_60", 41, 60),
    ("over_60", 61, None),
)


class ReportService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # --- Membership ---

    async def membership(self, year: int) -> dict[str, Any]:
        """The year's movement, and the club as it stood at the end of it.

        Opening is the closing count of the *previous* year rather than the
        count on 1 January, so that

            opening + joined - left = closing

        holds exactly. Read the other way round it does not: somebody who left
        on 1 January was a member on 31 December and is counted as having left
        this year, and an opening taken on 1 January would already have dropped
        them — the report would then be off by one and no one could see where.
        """
        opening_day = date(year - 1, 12, 31)
        closing_day = date(year, 12, 31)
        first_day = date(year, 1, 1)

        opening = await self._count_members_on(opening_day)
        closing = await self._count_members_on(closing_day)
        joined = await self._count_where(
            and_(Member.joined_at >= first_day, Member.joined_at <= closing_day)
        )
        left = await self._count_where(
            and_(
                Member.left_at.is_not(None),
                Member.left_at >= first_day,
                Member.left_at <= closing_day,
            )
        )

        return {
            "year": year,
            "opening": opening,
            "joined": joined,
            "left": left,
            "closing": closing,
            "by_category": await self._breakdown_on(closing_day, Member.category),
            "by_gender": await self._breakdown_on(closing_day, Member.gender),
            "by_age_band": await self._age_bands_on(closing_day),
            # Said out loud rather than silently absorbed: these are the rows
            # that make the four figures above disagree with what the club
            # believes, and only the club can fix them.
            "without_leaving_date": await self._count_where(
                and_(Member.status == "resigned", Member.left_at.is_(None))
            ),
            "without_birthday": await self._count_members_on(
                closing_day, extra=Member.birthday.is_(None)
            ),
        }

    async def _count_members_on(self, day: date, extra: Any = None) -> int:
        """The club's headcount at the *end* of [day].

        "Austritt zum 31.12." is the usual wording, and it means the membership
        runs out with that day: the member is in the previous year's closing
        balance and out of this one. So a leaving date on the day itself is
        already gone from the count — `left_at > day`, not `>=`.

        Written the other way round the report stops adding up. Somebody who
        left on 31 December would be counted both in the year's departures and
        in the balance at the end of it, and `opening + joined - left` would
        miss `closing` by exactly the people who left on the last day.
        """
        condition = and_(
            Member.joined_at <= day,
            or_(Member.left_at.is_(None), Member.left_at > day),
        )
        if extra is not None:
            condition = and_(condition, extra)
        return await self._count_where(condition)

    async def _count_where(self, condition: Any) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Member).where(self._scope()).where(condition)
        )
        return int(result.scalar_one())

    async def _breakdown_on(self, day: date, column: Any) -> list[dict[str, Any]]:
        """One row per distinct value, biggest first, nulls last.

        A null category is reported as its own row rather than dropped: "37
        members, of which 12 have no category" is a fact about the club's
        records, and hiding it makes the columns fail to add up.
        """
        query = (
            select(column, func.count())
            .select_from(Member)
            .where(self._scope())
            .where(Member.joined_at <= day)
            .where(or_(Member.left_at.is_(None), Member.left_at > day))
            .group_by(column)
        )
        result = await self.session.execute(query)
        rows = [{"value": row[0], "count": int(row[1])} for row in result.all()]
        return sorted(rows, key=lambda r: (r["value"] is None, -r["count"], r["value"] or ""))

    async def _age_bands_on(self, day: date) -> list[dict[str, Any]]:
        """Ages as of the last day of the year, which is what a report states.

        Computed in Python over the birthdays rather than in SQL: the bands are
        a product decision and belong where they can be read, and the row count
        here is the club's membership, not its history.
        """
        query = (
            select(Member.birthday)
            .where(self._scope())
            .where(Member.joined_at <= day)
            .where(or_(Member.left_at.is_(None), Member.left_at > day))
            .where(Member.birthday.is_not(None))
        )
        result = await self.session.execute(query)

        counts = {key: 0 for key, _, _ in AGE_BANDS}
        for (birthday,) in result.all():
            age = _age_on(birthday, day)
            for key, low, high in AGE_BANDS:
                if (low is None or age >= low) and (high is None or age <= high):
                    counts[key] += 1
                    break
        return [{"band": key, "count": counts[key]} for key, _, _ in AGE_BANDS]

    def _scope(self) -> Any:
        """Tenant and soft-delete, on every query in this file."""
        return and_(Member.tenant_id == self.tenant_id, Member.deleted_at.is_(None))

    # --- Dues ---

    async def dues(self, year: int) -> dict[str, Any]:
        """What was raised for the year, and what came in.

        Soll excludes cancelled dues — a cancelled charge was never owed, and
        counting it would make the payment rate say the club is behind on money
        it decided not to ask for. Cancelled is reported beside it so the
        decision stays visible rather than disappearing.
        """
        first_day = date(year, 1, 1)
        last_day = date(year, 12, 31)

        query = (
            select(
                Due.fee_name,
                Due.status,
                func.count(),
                func.coalesce(func.sum(Due.amount), 0),
            )
            .where(Due.tenant_id == self.tenant_id)
            .where(Due.deleted_at.is_(None))
            .where(Due.period_start >= first_day)
            .where(Due.period_start <= last_day)
            .group_by(Due.fee_name, Due.status)
        )
        result = await self.session.execute(query)

        fees: dict[str, dict[str, Any]] = {}
        for fee_name, status, count, amount in result.all():
            entry = fees.setdefault(
                fee_name,
                {
                    "fee_name": fee_name,
                    "count": 0,
                    "charged": Decimal("0"),
                    "paid": Decimal("0"),
                    "open": Decimal("0"),
                    "cancelled": Decimal("0"),
                    "cancelled_count": 0,
                },
            )
            amount = Decimal(amount)
            if status == "cancelled":
                entry["cancelled"] += amount
                entry["cancelled_count"] += int(count)
                continue
            entry["count"] += int(count)
            entry["charged"] += amount
            if status == "paid":
                entry["paid"] += amount
            else:
                entry["open"] += amount

        rows = sorted(fees.values(), key=lambda r: r["fee_name"])
        totals = {
            "count": sum(r["count"] for r in rows),
            "charged": sum((r["charged"] for r in rows), Decimal("0")),
            "paid": sum((r["paid"] for r in rows), Decimal("0")),
            "open": sum((r["open"] for r in rows), Decimal("0")),
            "cancelled": sum((r["cancelled"] for r in rows), Decimal("0")),
            "cancelled_count": sum(r["cancelled_count"] for r in rows),
        }
        return {"year": year, "by_fee": rows, "totals": totals}

    # --- Attendance ---

    async def attendance(self, year: int) -> dict[str, Any]:
        """Evenings held and visits recorded.

        Guests are counted in the visits and cannot be counted in the members:
        a guest has no member id, which is exactly what makes them a guest.
        Self-kept entries are separated out for the same reason the range list
        separates them — the club did not witness them.
        """
        first_day = date(year, 1, 1)
        last_day = date(year, 12, 31)

        sessions = await self.session.execute(
            select(func.count())
            .select_from(AttendanceSession)
            .where(AttendanceSession.tenant_id == self.tenant_id)
            .where(AttendanceSession.deleted_at.is_(None))
            .where(func.date(AttendanceSession.opens_at) >= first_day)
            .where(func.date(AttendanceSession.opens_at) <= last_day)
        )
        session_count = int(sessions.scalar_one())

        base = self._record_scope(first_day, last_day)
        totals = await self.session.execute(
            select(
                func.count(),
                func.count(distinct(AttendanceRecord.member_id)),
                func.count().filter(AttendanceRecord.origin == "external"),
                func.count().filter(AttendanceRecord.member_id.is_(None)),
            ).where(base)
        )
        records, members, self_kept, guests = totals.one()

        months = await self.session.execute(
            select(
                func.extract("month", AttendanceRecord.occurred_on),
                func.count(),
            )
            .where(base)
            .group_by(func.extract("month", AttendanceRecord.occurred_on))
        )
        per_month = {int(month): int(count) for month, count in months.all()}

        return {
            "year": year,
            "sessions": session_count,
            "records": int(records),
            "members": int(members),
            "guests": int(guests),
            "self_kept": int(self_kept),
            # Rounded to one place, and only when there were evenings at all:
            # "0.0 visits per evening" for a club that held none reads as a
            # turnout problem rather than as an empty year.
            "average_per_session": (
                round(int(records) / session_count, 1) if session_count else None
            ),
            "by_month": [{"month": m, "count": per_month.get(m, 0)} for m in range(1, 13)],
        }

    def _record_scope(self, first_day: date, last_day: date) -> Any:
        return and_(
            AttendanceRecord.tenant_id == self.tenant_id,
            AttendanceRecord.deleted_at.is_(None),
            AttendanceRecord.occurred_on >= first_day,
            AttendanceRecord.occurred_on <= last_day,
        )

    # --- Expenses ---

    async def expenses(self, year: int) -> dict[str, Any]:
        """What the club was invoiced, by supplier.

        The register's side of the year. Cancelled invoices are left out — the
        club decided it does not owe them — and rows that are still incomplete
        have no amount to add, so they are counted instead. A report that
        silently omitted four untyped scans would be a wrong report, and this
        is the one place where nobody would notice.

        Grouped by supplier rather than listed invoice by invoice: a
        Rechenschaftsbericht says what the club spent and roughly on what, and
        forty rows of individual invoices is the register's job, not this one.
        """
        first_day = date(year, 1, 1)
        last_day = date(year, 12, 31)

        scope = and_(
            IncomingInvoice.tenant_id == self.tenant_id,
            IncomingInvoice.deleted_at.is_(None),
            IncomingInvoice.status != "cancelled",
            IncomingInvoice.invoice_date >= first_day,
            IncomingInvoice.invoice_date <= last_day,
        )

        rows = await self.session.execute(
            select(
                IncomingInvoice.supplier_name,
                func.count(),
                func.coalesce(func.sum(IncomingInvoice.gross_amount), 0),
                func.coalesce(
                    func.sum(IncomingInvoice.gross_amount).filter(IncomingInvoice.status == "open"),
                    0,
                ),
            )
            .where(scope)
            .group_by(IncomingInvoice.supplier_name)
        )

        by_supplier = [
            {
                "supplier_name": supplier,
                "count": int(count),
                "total": Decimal(total),
                "open": Decimal(still_open),
            }
            for supplier, count, total, still_open in rows.all()
        ]
        # Biggest first: the reader is looking for what the money went on.
        by_supplier.sort(key=lambda row: (-row["total"], row["supplier_name"] or ""))

        incomplete = await self.session.execute(
            select(func.count())
            .select_from(IncomingInvoice)
            .where(
                and_(
                    IncomingInvoice.tenant_id == self.tenant_id,
                    IncomingInvoice.deleted_at.is_(None),
                    IncomingInvoice.status != "cancelled",
                )
            )
            .where(
                or_(
                    IncomingInvoice.gross_amount.is_(None),
                    IncomingInvoice.invoice_date.is_(None),
                    IncomingInvoice.supplier_name.is_(None),
                    IncomingInvoice.invoice_number.is_(None),
                )
            )
        )

        return {
            "year": year,
            "by_supplier": by_supplier,
            "total": sum((row["total"] for row in by_supplier), Decimal("0")),
            "open": sum((row["open"] for row in by_supplier), Decimal("0")),
            "count": sum(row["count"] for row in by_supplier),
            # Not year-filtered: a row with no date belongs to no year, and it
            # is exactly the row that would otherwise never be chased.
            "incomplete_count": int(incomplete.scalar_one()),
        }

    # --- The whole report ---

    async def annual(self, year: int) -> dict[str, Any]:
        return {
            "year": year,
            "years": await self.available_years(),
            "membership": await self.membership(year),
            "dues": await self.dues(year),
            "expenses": await self.expenses(year),
            "attendance": await self.attendance(year),
        }

    async def available_years(self) -> list[int]:
        """Years the club could sensibly report on, newest first.

        From its earliest joining date to the current one in the club's own
        zone — a report for next year is not a thing, and a picker that offers
        it invites an empty page nobody can explain.
        """
        current = await self.current_year()
        result = await self.session.execute(select(func.min(Member.joined_at)).where(self._scope()))
        earliest = result.scalar_one_or_none()
        first = earliest.year if earliest else current
        return list(range(current, min(first, current) - 1, -1))

    async def current_year(self) -> int:
        """The club's year, not the server's.

        Between midnight in Berlin and midnight in UTC these differ, and on
        31 December they differ by a whole reporting period.
        """
        result = await self.session.execute(
            select(Tenant.timezone).where(Tenant.id == self.tenant_id)
        )
        name = result.scalar_one_or_none()
        try:
            zone = ZoneInfo(name) if name else ZoneInfo("UTC")
        except Exception:  # An unknown zone must not break a report.
            zone = ZoneInfo("UTC")
        return datetime.now(UTC).astimezone(zone).year


def _age_on(birthday: date, day: date) -> int:
    """Full years lived on [day]. The birthday itself counts as reached."""
    had_birthday = (day.month, day.day) >= (birthday.month, birthday.day)
    return day.year - birthday.year - (0 if had_birthday else 1)
