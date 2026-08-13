"""The annual figures, and the arithmetic a Kassenprüfer checks first."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord, AttendanceSession
from app.models.due import Due, FeeType
from app.models.incoming_invoice import IncomingInvoice
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import User

pytestmark = pytest.mark.asyncio

YEAR = 2025


async def a_member(
    db_session: AsyncSession,
    tenant: Tenant,
    user: User,
    *,
    joined: date,
    left: date | None = None,
    number: str | None = None,
    **kw: object,
) -> Member:
    member = Member(
        tenant_id=tenant.id,
        member_number=number or uuid.uuid4().hex[:8],
        first_name=str(kw.pop("first_name", "Erika")),
        last_name=str(kw.pop("last_name", "Mustermann")),
        joined_at=joined,
        left_at=left,
        status=str(kw.pop("status", "active")),
        created_by=user.id,
        updated_by=user.id,
        **kw,
    )
    db_session.add(member)
    await db_session.flush()
    return member


async def a_due(
    db_session: AsyncSession,
    tenant: Tenant,
    user: User,
    member: Member,
    fee: FeeType,
    *,
    amount: str,
    status: str = "open",
    year: int = YEAR,
    fee_name: str = "Erwachsene",
) -> Due:
    due = Due(
        tenant_id=tenant.id,
        member_id=member.id,
        fee_type_id=fee.id,
        fee_name=fee_name,
        amount=Decimal(amount),
        period_start=date(year, 1, 1),
        period_end=date(year, 12, 31),
        due_date=date(year, 1, 31),
        status=status,
        created_by=user.id,
        updated_by=user.id,
    )
    db_session.add(due)
    await db_session.flush()
    return due


async def a_fee(db_session: AsyncSession, tenant: Tenant, user: User) -> FeeType:
    fee = FeeType(
        tenant_id=tenant.id,
        name="Erwachsene",
        amount=Decimal("120.00"),
        interval="yearly",
        created_by=user.id,
        updated_by=user.id,
    )
    db_session.add(fee)
    await db_session.flush()
    return fee


# --- Membership ---


async def test_the_movement_adds_up(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """opening + joined - left == closing, or the report cannot be read out.

    Every awkward case is in here at once, because they only disagree in
    combination: somebody who joined and left in the same year, somebody who
    left on the first day, somebody who left on the last.
    """
    await a_member(db_session, test_tenant, test_user, joined=date(2019, 5, 1))
    await a_member(db_session, test_tenant, test_user, joined=date(YEAR, 3, 1))
    await a_member(
        db_session, test_tenant, test_user, joined=date(YEAR, 4, 1), left=date(YEAR, 9, 1)
    )
    await a_member(
        db_session, test_tenant, test_user, joined=date(2018, 1, 1), left=date(YEAR, 1, 1)
    )
    await a_member(
        db_session, test_tenant, test_user, joined=date(2017, 1, 1), left=date(YEAR, 12, 31)
    )

    response = await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")
    assert response.status_code == 200, response.text

    data = response.json()["data"]["membership"]
    assert data["opening"] + data["joined"] - data["left"] == data["closing"]
    # Spelled out, so a change to the boundary rules is visible here rather
    # than only in the identity above.
    assert data["opening"] == 3
    assert data["joined"] == 2
    assert data["left"] == 3
    assert data["closing"] == 2


async def test_somebody_who_left_on_new_years_day_was_a_member_last_year(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The reason `opening` is the previous year's closing, not 1 January."""
    await a_member(
        db_session, test_tenant, test_user, joined=date(2020, 1, 1), left=date(YEAR, 1, 1)
    )

    data = (await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")).json()["data"]
    assert data["membership"]["opening"] == 1
    assert data["membership"]["left"] == 1
    assert data["membership"]["closing"] == 0


async def test_a_member_of_another_club_is_not_counted(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    other = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other)
    await db_session.flush()
    await a_member(db_session, other, test_user, joined=date(2020, 1, 1))
    await a_member(db_session, test_tenant, test_user, joined=date(2020, 1, 1))

    data = (await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")).json()["data"]
    assert data["membership"]["closing"] == 1


async def test_the_age_bands_are_taken_at_the_end_of_the_year(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A report states ages as of the reporting date, not as of today."""
    # Turns 18 on 30 December of the reporting year: an adult in this report,
    # a youth in the one before it.
    await a_member(
        db_session,
        test_tenant,
        test_user,
        joined=date(2020, 1, 1),
        birthday=date(YEAR - 18, 12, 30),
    )
    await a_member(
        db_session,
        test_tenant,
        test_user,
        joined=date(2020, 1, 1),
        birthday=date(YEAR - 17, 1, 2),
    )

    data = (await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")).json()["data"]
    bands = {row["band"]: row["count"] for row in data["membership"]["by_age_band"]}
    assert bands["under_18"] == 1
    assert bands["18_to_26"] == 1


async def test_members_without_a_birthday_are_counted_but_not_banded(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """Otherwise the age table quietly fails to add up to the membership."""
    await a_member(db_session, test_tenant, test_user, joined=date(2020, 1, 1))

    data = (await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")).json()["data"]
    membership = data["membership"]
    assert membership["closing"] == 1
    assert sum(row["count"] for row in membership["by_age_band"]) == 0
    assert membership["without_birthday"] == 1


async def test_a_resignation_without_a_date_is_reported_not_absorbed(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """They still count as present, so the club has to be told why."""
    await a_member(
        db_session,
        test_tenant,
        test_user,
        joined=date(2020, 1, 1),
        status="resigned",
    )

    data = (await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")).json()["data"]
    assert data["membership"]["closing"] == 1
    assert data["membership"]["without_leaving_date"] == 1


# --- Dues ---


async def test_cancelled_dues_are_not_owed(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """Counting them would say the club is behind on money it never asked for."""
    fee = await a_fee(db_session, test_tenant, test_user)
    # One due per member, fee type and period is a database constraint, so
    # three charges means three members.
    for amount, status in (("120.00", "paid"), ("80.00", "open"), ("50.00", "cancelled")):
        member = await a_member(db_session, test_tenant, test_user, joined=date(2020, 1, 1))
        await a_due(db_session, test_tenant, test_user, member, fee, amount=amount, status=status)

    data = (await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")).json()["data"]
    totals = data["dues"]["totals"]
    assert totals["charged"] == "200.00"
    assert totals["paid"] == "120.00"
    assert totals["open"] == "80.00"
    assert totals["cancelled"] == "50.00"
    assert totals["count"] == 2


async def test_dues_of_another_year_stay_out(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    member = await a_member(db_session, test_tenant, test_user, joined=date(2020, 1, 1))
    fee = await a_fee(db_session, test_tenant, test_user)
    await a_due(db_session, test_tenant, test_user, member, fee, amount="120.00", year=YEAR)
    await a_due(db_session, test_tenant, test_user, member, fee, amount="99.00", year=YEAR - 1)

    data = (await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")).json()["data"]
    assert data["dues"]["totals"]["charged"] == "120.00"


# --- Attendance ---


async def test_guests_count_as_visits_and_not_as_members(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    member = await a_member(db_session, test_tenant, test_user, joined=date(2020, 1, 1))

    # Two evenings, because a member can only be checked into one session once
    # — which is also what makes "seen twice" one member rather than two.
    sessions = []
    for day in (6, 13):
        session = AttendanceSession(
            tenant_id=test_tenant.id,
            title="Übungsabend",
            opens_at=datetime(YEAR, 5, day, 17, 0, tzinfo=UTC),
            closes_at=datetime(YEAR, 5, day, 21, 0, tzinfo=UTC),
            created_by=test_user.id,
            updated_by=test_user.id,
        )
        db_session.add(session)
        sessions.append((session, day))
    await db_session.flush()

    rows = [
        (sessions[0][0], sessions[0][1], member.id, None),
        (sessions[1][0], sessions[1][1], member.id, None),
        (sessions[0][0], sessions[0][1], None, "Besuch"),
    ]
    for session, day, member_id, guest in rows:
        db_session.add(
            AttendanceRecord(
                tenant_id=test_tenant.id,
                session_id=session.id,
                member_id=member_id,
                guest_name=guest,
                occurred_on=date(YEAR, 5, day),
                checked_in_at=datetime(YEAR, 5, day, 18, 0, tzinfo=UTC),
                created_by=test_user.id,
                updated_by=test_user.id,
            )
        )
    await db_session.flush()

    data = (await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")).json()["data"]
    attendance = data["attendance"]
    assert attendance["sessions"] == 2
    assert attendance["records"] == 3
    # One person seen twice is one member; the guest has no member id at all.
    assert attendance["members"] == 1
    assert attendance["guests"] == 1
    assert attendance["average_per_session"] == 1.5
    assert attendance["by_month"][4] == {"month": 5, "count": 3}


async def test_a_year_without_sessions_has_no_average(
    auth_client: AsyncClient,
) -> None:
    """0.0 visits per evening would read as a turnout problem, not an empty year."""
    data = (await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")).json()["data"]
    assert data["attendance"]["sessions"] == 0
    assert data["attendance"]["average_per_session"] is None


# --- The export and the door ---


async def test_the_export_is_a_spreadsheet_a_german_excel_can_read(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    member = await a_member(db_session, test_tenant, test_user, joined=date(2020, 1, 1))
    fee = await a_fee(db_session, test_tenant, test_user)
    await a_due(db_session, test_tenant, test_user, member, fee, amount="120.50", status="paid")

    response = await auth_client.get(f"/api/v1/reports/annual/export?year={YEAR}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "jahresbericht-2025.csv" in response.headers["content-disposition"]

    body = response.text
    # The BOM, or Excel reads it as Latin-1 and prints "BeitrÃ¤ge".
    assert body.startswith("﻿")
    assert "Mitgliederentwicklung;2025" in body
    # Semicolons and a decimal comma, together — either alone lands the whole
    # file in one column or multiplies the amount by a hundred.
    assert "120,50" in body


async def test_the_report_is_board_work(anon_client: AsyncClient) -> None:
    assert (await anon_client.get("/api/v1/reports/annual")).status_code == 403
    assert (await anon_client.get("/api/v1/reports/annual/export")).status_code == 403


async def test_the_year_picker_stops_at_the_current_year(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A report for next year is not a thing, and an empty page is unexplainable."""
    await a_member(db_session, test_tenant, test_user, joined=date(2019, 6, 1))

    data = (await auth_client.get("/api/v1/reports/annual")).json()["data"]
    assert data["years"][0] == data["year"]
    assert data["years"][-1] == 2019
    assert data["years"] == sorted(data["years"], reverse=True)


# --- Expenses ---


async def an_invoice(
    db_session: AsyncSession,
    tenant: Tenant,
    user: User,
    *,
    supplier: str | None = "Sportgeräte Müller",
    number: str | None = "RE-1",
    on: date | None = date(YEAR, 5, 4),
    gross: str | None = "100.00",
    status: str = "open",
) -> IncomingInvoice:
    invoice = IncomingInvoice(
        tenant_id=tenant.id,
        supplier_name=supplier,
        invoice_number=number,
        invoice_date=on,
        gross_amount=Decimal(gross) if gross is not None else None,
        status=status,
        storage_key=f"{tenant.id}/{uuid.uuid4().hex}",
        original_filename="rechnung.pdf",
        content_type="application/pdf",
        byte_size=10,
        checksum_sha256="0" * 64,
        uploaded_at=datetime.now(UTC),
        created_by=user.id,
        updated_by=user.id,
    )
    db_session.add(invoice)
    await db_session.flush()
    return invoice


async def test_expenses_are_grouped_by_supplier_biggest_first(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A report says what the money went on, not what forty invoices said."""
    await an_invoice(
        db_session, test_tenant, test_user, supplier="Klein", number="K-1", gross="50.00"
    )
    await an_invoice(
        db_session, test_tenant, test_user, supplier="Groß", number="G-1", gross="300.00"
    )
    await an_invoice(
        db_session,
        test_tenant,
        test_user,
        supplier="Groß",
        number="G-2",
        gross="200.00",
        status="paid",
    )

    data = (await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")).json()["data"]
    expenses = data["expenses"]

    assert [row["supplier_name"] for row in expenses["by_supplier"]] == ["Groß", "Klein"]
    assert expenses["by_supplier"][0]["total"] == "500.00"
    # Only what is still owed, not the whole supplier.
    assert expenses["by_supplier"][0]["open"] == "300.00"
    assert expenses["total"] == "550.00"
    assert expenses["count"] == 3


async def test_a_cancelled_invoice_is_not_an_expense(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The club decided it does not owe it — the same rule the register uses."""
    await an_invoice(db_session, test_tenant, test_user, number="A-1", gross="100.00")
    await an_invoice(
        db_session, test_tenant, test_user, number="A-2", gross="900.00", status="cancelled"
    )

    data = (await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")).json()["data"]
    assert data["expenses"]["total"] == "100.00"
    assert data["expenses"]["count"] == 1


async def test_an_invoice_of_another_year_is_not_in_this_one(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await an_invoice(db_session, test_tenant, test_user, number="B-1", on=date(YEAR - 1, 12, 31))

    data = (await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")).json()["data"]
    assert data["expenses"]["count"] == 0


async def test_an_untyped_scan_is_counted_rather_than_summed(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """It has no date, so it belongs to no year — and it is exactly the row
    that would otherwise never be chased."""
    await an_invoice(
        db_session,
        test_tenant,
        test_user,
        supplier=None,
        number=None,
        on=None,
        gross=None,
    )

    data = (await auth_client.get(f"/api/v1/reports/annual?year={YEAR}")).json()["data"]
    assert data["expenses"]["count"] == 0
    assert data["expenses"]["incomplete_count"] == 1


async def test_the_export_carries_the_expenses_too(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await an_invoice(db_session, test_tenant, test_user, gross="120.50")

    body = (await auth_client.get(f"/api/v1/reports/annual/export?year={YEAR}")).text
    assert "Ausgaben;2025" in body
    assert "Sportgeräte Müller;1;120,50;120,50" in body
