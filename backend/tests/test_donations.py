"""Donation receipts: the prescribed form, and the two refusals that matter."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.donation import DonationReceipt
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import User
from app.services.amount_in_words import euros_in_words

pytestmark = pytest.mark.asyncio


async def a_recognised_club(
    db_session: AsyncSession, tenant: Tenant, *, fees_deductible: bool = False
) -> None:
    """The tax data a receipt has to state. A club without it cannot issue."""
    tenant.nonprofit_purposes = "Förderung des Sports"
    tenant.tax_exemption_kind = "freistellungsbescheid"
    tenant.tax_exemption_date = date(2025, 3, 14)
    tenant.tax_exemption_period = 2024
    tenant.tax_office = "Finanzamt Musterstadt"
    tenant.tax_number = "123/456/78901"
    tenant.membership_fees_deductible = fees_deductible
    await db_session.flush()


async def a_member(db_session: AsyncSession, tenant: Tenant, user: User, **kw: object) -> Member:
    member = Member(
        tenant_id=tenant.id,
        member_number=str(kw.pop("member_number", "0042")),
        first_name=str(kw.pop("first_name", "Erika")),
        last_name=str(kw.pop("last_name", "Mustermann")),
        joined_at=date(2020, 1, 1),
        status="active",
        created_by=user.id,
        updated_by=user.id,
        **kw,
    )
    db_session.add(member)
    await db_session.flush()
    return member


def donation(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "donor_name": "Erika Mustermann",
        "amount": "250.00",
        "received_on": date.today().isoformat(),
        "kind": "geldzuwendung",
    }
    payload.update(overrides)
    return payload


# --- The refusal that costs money if it is missing ---


async def test_a_sports_club_cannot_certify_a_membership_fee(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """Fees to a club promoting sport are not deductible (§ 10b Abs. 1 Satz 8
    EStG). Certifying one hands the member a receipt the tax office rejects
    and puts the club on the hook for the tax."""
    await a_recognised_club(db_session, test_tenant, fees_deductible=False)

    response = await auth_client.post("/api/v1/donations", json=donation(kind="mitgliedsbeitrag"))
    assert response.status_code == 422
    assert "membership_fees_not_deductible" in response.text

    # The donation itself is fine — only the kind was refused.
    assert (await auth_client.post("/api/v1/donations", json=donation())).status_code == 201


async def test_a_club_whose_purposes_allow_it_may_certify_a_fee(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await a_recognised_club(db_session, test_tenant, fees_deductible=True)

    response = await auth_client.post("/api/v1/donations", json=donation(kind="mitgliedsbeitrag"))
    assert response.status_code == 201
    assert response.json()["data"]["kind"] == "mitgliedsbeitrag"


async def test_incomplete_tax_data_blocks_issuing(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """A receipt that looks official and asserts nothing is worse than none."""
    response = await auth_client.post("/api/v1/donations", json=donation())
    assert response.status_code == 422

    missing = {d["field"] for d in response.json()["details"]}
    assert "tax_number" in missing
    assert "nonprofit_purposes" in missing


async def test_a_freistellungsbescheid_needs_its_assessment_period(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await a_recognised_club(db_session, test_tenant)
    test_tenant.tax_exemption_period = None
    await db_session.flush()

    response = await auth_client.post("/api/v1/donations", json=donation())
    assert response.status_code == 422
    assert "tax_exemption_period" in response.text


async def test_a_60a_determination_needs_no_period(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """A newly founded club has no assessed period yet, and the form says so
    differently."""
    await a_recognised_club(db_session, test_tenant)
    test_tenant.tax_exemption_kind = "feststellung_60a"
    test_tenant.tax_exemption_period = None
    await db_session.flush()

    assert (await auth_client.post("/api/v1/donations", json=donation())).status_code == 201


async def test_readiness_says_what_is_missing_before_the_form(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    empty = (await auth_client.get("/api/v1/donations/readiness")).json()["data"]
    assert empty["ready"] is False
    assert "tax_number" in empty["missing"]

    await a_recognised_club(db_session, test_tenant)
    ready = (await auth_client.get("/api/v1/donations/readiness")).json()["data"]
    assert ready["ready"] is True
    assert ready["missing"] == []
    assert ready["membership_fees_deductible"] is False


# --- What the receipt freezes ---


async def test_the_receipt_freezes_the_clubs_tax_data(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """A receipt from 2024 has to keep saying what was true in 2024."""
    await a_recognised_club(db_session, test_tenant)
    issued = (await auth_client.post("/api/v1/donations", json=donation())).json()["data"]

    assert issued["tax_number"] == "123/456/78901"
    assert issued["purposes"] == "Förderung des Sports"
    assert issued["exemption_period"] == 2024

    # The club is reassessed. What was handed out must not change.
    test_tenant.tax_number = "999/999/99999"
    test_tenant.nonprofit_purposes = "Förderung der Jugendhilfe"
    await db_session.flush()

    again = (await auth_client.get("/api/v1/donations")).json()["data"][0]
    assert again["tax_number"] == "123/456/78901"
    assert again["purposes"] == "Förderung des Sports"


async def test_a_member_donor_is_named_from_the_register(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A name that differs from the register by a typo is one somebody has to
    explain."""
    await a_recognised_club(db_session, test_tenant)
    member = await a_member(
        db_session,
        test_tenant,
        test_user,
        street="Musterweg 1",
        zip_code="12345",
        city="Musterstadt",
    )

    response = await auth_client.post(
        "/api/v1/donations",
        json=donation(member_id=str(member.id), donor_name="Falsch Geschrieben"),
    )
    assert response.status_code == 201

    data = response.json()["data"]
    assert data["donor_name"] == "Erika Mustermann"
    assert data["donor_address"] == "Musterweg 1, 12345 Musterstadt"


async def test_a_donor_who_is_not_a_member_is_accepted(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await a_recognised_club(db_session, test_tenant)

    response = await auth_client.post(
        "/api/v1/donations",
        json=donation(donor_name="Firma Beispiel GmbH", donor_address="Weg 2, 12345 Ort"),
    )
    assert response.status_code == 201
    assert response.json()["data"]["member_id"] is None


async def test_a_receipt_needs_a_donor(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await a_recognised_club(db_session, test_tenant)
    payload = donation()
    del payload["donor_name"]

    assert (await auth_client.post("/api/v1/donations", json=payload)).status_code == 422


async def test_a_receipt_over_nothing_is_refused(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await a_recognised_club(db_session, test_tenant)

    for amount in ("0.00", "-5.00"):
        response = await auth_client.post("/api/v1/donations", json=donation(amount=amount))
        assert response.status_code == 422, amount


async def test_money_that_has_not_arrived_is_refused(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await a_recognised_club(db_session, test_tenant)
    tomorrow = (date.today() + timedelta(days=2)).isoformat()

    response = await auth_client.post("/api/v1/donations", json=donation(received_on=tomorrow))
    assert response.status_code == 422


async def test_another_clubs_receipt_is_not_found(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    other = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other)
    await db_session.flush()
    foreign = DonationReceipt(
        tenant_id=other.id,
        donor_name="Fremd",
        amount=Decimal("10.00"),
        received_on=date.today(),
        kind="geldzuwendung",
        club_name="Other Club",
        exemption_kind="freistellungsbescheid",
        exemption_date=date(2025, 1, 1),
        tax_office="FA",
        tax_number="1",
        purposes="Sport",
        issued_at=datetime.now(UTC),
        issued_by_user_id=uuid.uuid4(),
        verification_code="FOREIGNCODE",
        content_hash="x",
    )
    db_session.add(foreign)
    await db_session.flush()

    assert (await auth_client.get(f"/api/v1/donations/{foreign.id}/pdf")).status_code == 404
    assert (
        await auth_client.post(f"/api/v1/donations/{foreign.id}/revoke", json={"reason": "nope"})
    ).status_code == 404


async def test_receipts_need_a_signed_in_caller(anon_client: AsyncClient) -> None:
    assert (await anon_client.get("/api/v1/donations")).status_code == 403
    assert (await anon_client.post("/api/v1/donations", json=donation())).status_code == 403


# --- Revocation, PDF, check page ---


async def test_revoking_keeps_the_receipt(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """The donor holds the paper and the tax office may have seen it."""
    await a_recognised_club(db_session, test_tenant)
    issued = (await auth_client.post("/api/v1/donations", json=donation())).json()["data"]

    revoked = await auth_client.post(
        f"/api/v1/donations/{issued['id']}/revoke", json={"reason": "Betrag falsch"}
    )
    assert revoked.status_code == 200
    assert revoked.json()["data"]["revoked_at"] is not None
    assert revoked.json()["data"]["amount"] == issued["amount"]

    again = await auth_client.post(
        f"/api/v1/donations/{issued['id']}/revoke", json={"reason": "nochmal"}
    )
    assert again.status_code == 409


async def test_the_pdf_renders(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await a_recognised_club(db_session, test_tenant)
    issued = (await auth_client.post("/api/v1/donations", json=donation())).json()["data"]

    response = await auth_client.get(f"/api/v1/donations/{issued['id']}/pdf")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["cache-control"] == "no-store"
    assert "zuwendungsbestaetigung" in response.headers["content-disposition"]


async def test_the_check_page_confirms_without_naming_the_amount(
    auth_client: AsyncClient,
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    """A donation is nobody else's business; the page only says it is real."""
    await a_recognised_club(db_session, test_tenant)
    issued = (await auth_client.post("/api/v1/donations", json=donation(amount="1234.00"))).json()[
        "data"
    ]

    response = await anon_client.get(f"/verify/{issued['verification_code']}")
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["kind"] == "donation_receipt"
    assert data["valid"] is True
    assert data["member_name"] == "E. Mustermann"
    assert "amount" not in data
    assert "1234" not in response.text


async def test_the_check_page_reports_a_revoked_receipt(
    auth_client: AsyncClient,
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    await a_recognised_club(db_session, test_tenant)
    issued = (await auth_client.post("/api/v1/donations", json=donation())).json()["data"]
    await auth_client.post(f"/api/v1/donations/{issued['id']}/revoke", json={"reason": "Ersetzt"})

    data = (await anon_client.get(f"/verify/{issued['verification_code']}")).json()["data"]
    assert data["valid"] is False
    assert data["revoked"] is True


async def test_filtering_by_year(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """The tax year is how a club looks at these."""
    await a_recognised_club(db_session, test_tenant)
    this_year = date.today()
    last_year = date(this_year.year - 1, 6, 1)

    await auth_client.post("/api/v1/donations", json=donation(received_on=this_year.isoformat()))
    await auth_client.post("/api/v1/donations", json=donation(received_on=last_year.isoformat()))

    listed = await auth_client.get(f"/api/v1/donations?year={last_year.year}")
    assert len(listed.json()["data"]) == 1
    assert listed.json()["data"][0]["received_on"].startswith(str(last_year.year))


# --- The amount in words ---


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("1.00", "ein Euro 00 Cent"),
        ("0.50", "null Euro 50 Cent"),
        ("21.00", "einundzwanzig Euro 00 Cent"),
        ("100.00", "einhundert Euro 00 Cent"),
        ("1000.00", "eintausend Euro 00 Cent"),
        ("1234.50", "eintausendzweihundertvierunddreißig Euro 50 Cent"),
        ("2500000.00", "zwei Millionen fünfhunderttausend Euro 00 Cent"),
    ],
)
async def test_amounts_are_written_out_in_german(amount: str, expected: str) -> None:
    """The form asks for figures *and* words: a figure can be altered with a
    pen and a word cannot. So this has to be right."""
    assert euros_in_words(Decimal(amount)) == expected
