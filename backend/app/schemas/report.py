"""Response models for the annual report.

Everything here is a figure the club will read out at a general meeting, so the
names are the ones the report uses rather than the ones the tables use.
"""

from decimal import Decimal

from app.schemas.base import BaseSchema


class CountByValue(BaseSchema):
    """One row of a breakdown. `value` is null for records that carry none."""

    value: str | None = None
    count: int


class CountByBand(BaseSchema):
    band: str
    count: int


class MembershipReport(BaseSchema):
    year: int
    #: The closing count of the previous year, so that
    #: `opening + joined - left == closing` holds exactly.
    opening: int
    joined: int
    left: int
    closing: int
    by_category: list[CountByValue]
    by_gender: list[CountByValue]
    by_age_band: list[CountByBand]
    #: Members marked as resigned with no leaving date. They still count as
    #: present above, which is why the number is stated rather than absorbed.
    without_leaving_date: int
    #: Members with no birthday on file — the age bands cannot see them.
    without_birthday: int


class DuesReportRow(BaseSchema):
    fee_name: str
    count: int
    #: Excludes cancelled dues: a cancelled charge was never owed.
    charged: Decimal
    paid: Decimal
    open: Decimal
    cancelled: Decimal
    cancelled_count: int


class DuesReportTotals(BaseSchema):
    count: int
    charged: Decimal
    paid: Decimal
    open: Decimal
    cancelled: Decimal
    cancelled_count: int


class DuesReport(BaseSchema):
    year: int
    by_fee: list[DuesReportRow]
    totals: DuesReportTotals


class MonthCount(BaseSchema):
    month: int
    count: int


class AttendanceReport(BaseSchema):
    year: int
    sessions: int
    records: int
    #: Distinct members seen. Guests cannot be in here — they have no member id.
    members: int
    guests: int
    self_kept: int
    #: Null when the club held no sessions, rather than 0.0.
    average_per_session: float | None = None
    by_month: list[MonthCount]


class AnnualReport(BaseSchema):
    year: int
    #: What the year picker may offer, newest first.
    years: list[int]
    membership: MembershipReport
    dues: DuesReport
    attendance: AttendanceReport
