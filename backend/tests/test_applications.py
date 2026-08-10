"""The join form and the decision on what it produces."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import MembershipApplication
from app.models.consent import MemberConsent
from app.models.division import Division
from app.models.due import FeeType, MemberFee
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import User

pytestmark = pytest.mark.asyncio


def form(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "first_name": "Jonas",
        "last_name": "Weber",
        "email": "jonas.weber@example.com",
        "privacy_accepted": True,
    }
    body.update(overrides)
    return body


async def open_the_form(db_session: AsyncSession, tenant: Tenant) -> None:
    tenant.applications_enabled = True
    await db_session.flush()


async def a_fee(db_session: AsyncSession, tenant: Tenant, user: User, **kw: object) -> FeeType:
    fee = FeeType(
        tenant_id=tenant.id,
        name=str(kw.get("name", "Erwachsene")),
        amount=Decimal("120.00"),
        interval="yearly",
        is_active=bool(kw.get("is_active", True)),
        created_by=user.id,
        updated_by=user.id,
    )
    db_session.add(fee)
    await db_session.flush()
    return fee


async def an_application(
    db_session: AsyncSession, tenant: Tenant, **kw: object
) -> MembershipApplication:
    application = MembershipApplication(
        tenant_id=tenant.id,
        status="pending",
        first_name=str(kw.get("first_name", "Jonas")),
        last_name="Weber",
        email="jonas.weber@example.com",
        privacy_accepted_at=datetime.now(UTC),
        **{k: v for k, v in kw.items() if k not in {"first_name"}},
    )
    db_session.add(application)
    await db_session.flush()
    return application


# --- The public form ---


async def test_form_is_closed_unless_the_club_opened_it(
    anon_client: AsyncClient, test_tenant: Tenant
) -> None:
    """A club that never asked for a public form does not have one.

    404 rather than 403: a closed form must not confirm that the club exists.
    """
    response = await anon_client.get(f"/join/{test_tenant.slug}")
    assert response.status_code == 404

    submitted = await anon_client.post(f"/join/{test_tenant.slug}", json=form())
    assert submitted.status_code == 404


async def test_unknown_club_answers_exactly_like_a_closed_one(
    anon_client: AsyncClient, test_tenant: Tenant
) -> None:
    """Otherwise the join page becomes a way to enumerate the clubs here."""
    closed = await anon_client.get(f"/join/{test_tenant.slug}")
    unknown = await anon_client.get("/join/no-such-club")

    assert closed.status_code == unknown.status_code == 404
    assert closed.json() == unknown.json()


async def test_form_offers_only_what_the_club_sells(
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await open_the_form(db_session, test_tenant)
    await a_fee(db_session, test_tenant, test_user, name="Erwachsene")
    await a_fee(db_session, test_tenant, test_user, name="Ausgetreten", is_active=False)

    response = await anon_client.get(f"/join/{test_tenant.slug}")
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["club_name"] == test_tenant.name
    assert [f["name"] for f in data["fee_types"]] == ["Erwachsene"]


async def test_form_hides_divisions_when_the_club_does_not_use_them(
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The primary division of a single-sport club is an internal detail."""
    await open_the_form(db_session, test_tenant)
    db_session.add(
        Division(
            tenant_id=test_tenant.id,
            name="Hauptsparte",
            is_primary=True,
            created_by=test_user.id,
            updated_by=test_user.id,
        )
    )
    await db_session.flush()

    response = await anon_client.get(f"/join/{test_tenant.slug}")
    assert response.json()["data"]["divisions"] == []

    test_tenant.has_divisions = True
    await db_session.flush()

    response = await anon_client.get(f"/join/{test_tenant.slug}")
    assert [d["name"] for d in response.json()["data"]["divisions"]] == ["Hauptsparte"]


async def test_submitting_creates_an_application_and_no_member(
    anon_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """The whole point of the split: a form does not admit anybody."""
    await open_the_form(db_session, test_tenant)

    response = await anon_client.post(f"/join/{test_tenant.slug}", json=form())
    assert response.status_code == 201

    applications = (
        (
            await db_session.execute(
                select(MembershipApplication).where(
                    MembershipApplication.tenant_id == test_tenant.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(applications) == 1
    assert applications[0].status == "pending"
    assert applications[0].decided_at is None

    members = (
        (await db_session.execute(select(Member).where(Member.tenant_id == test_tenant.id)))
        .scalars()
        .all()
    )
    assert members == []


async def test_receipt_says_nothing_the_sender_could_mine(
    anon_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """No id, no member, no hint about who is already in the club."""
    await open_the_form(db_session, test_tenant)

    response = await anon_client.post(f"/join/{test_tenant.slug}", json=form())
    assert response.json() == {"data": {"received": True}}


async def test_a_known_member_gets_the_same_answer_as_a_stranger(
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """Otherwise the form answers "is this person a member of your club?"."""
    await open_the_form(db_session, test_tenant)
    db_session.add(
        Member(
            tenant_id=test_tenant.id,
            member_number="001",
            first_name="Jonas",
            last_name="Weber",
            email="jonas.weber@example.com",
            joined_at=date.today(),
            created_by=test_user.id,
            updated_by=test_user.id,
        )
    )
    await db_session.flush()

    stranger = await anon_client.post(
        f"/join/{test_tenant.slug}", json=form(email="unknown@example.com")
    )
    member = await anon_client.post(f"/join/{test_tenant.slug}", json=form())

    assert stranger.status_code == member.status_code == 201
    assert stranger.json() == member.json()


async def test_privacy_notice_is_a_precondition(
    anon_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await open_the_form(db_session, test_tenant)

    response = await anon_client.post(
        f"/join/{test_tenant.slug}", json=form(privacy_accepted=False)
    )
    assert response.status_code == 422


async def test_a_fee_the_club_does_not_offer_is_refused(
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A stored wish nobody can fulfil would read as a promise at the decision."""
    await open_the_form(db_session, test_tenant)
    retired = await a_fee(db_session, test_tenant, test_user, name="Alt", is_active=False)

    response = await anon_client.post(
        f"/join/{test_tenant.slug}", json=form(fee_type_id=str(retired.id))
    )
    assert response.status_code == 422


async def test_a_fee_from_another_club_is_refused(
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await open_the_form(db_session, test_tenant)
    other = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other)
    await db_session.flush()
    foreign = await a_fee(db_session, other, test_user)

    response = await anon_client.post(
        f"/join/{test_tenant.slug}", json=form(fee_type_id=str(foreign.id))
    )
    assert response.status_code == 422


async def test_a_mandate_without_an_account_is_refused(
    anon_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    await open_the_form(db_session, test_tenant)

    response = await anon_client.post(
        f"/join/{test_tenant.slug}", json=form(grant_sepa_mandate=True)
    )
    assert response.status_code == 422


# --- The board's side ---


async def test_applications_need_the_board(
    anon_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    application = await an_application(db_session, test_tenant)

    # 403 rather than 401 throughout this API — see the auth dependency.
    assert (await anon_client.get("/api/v1/applications")).status_code == 403
    assert (
        await anon_client.post(f"/api/v1/applications/{application.id}/accept")
    ).status_code == 403


async def test_the_list_withholds_the_bank_details(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """Scanning twenty applications is no reason to be handed twenty IBANs."""
    await an_application(
        db_session,
        test_tenant,
        iban="DE02120300000000202051",
        sepa_mandate_date=date.today(),
    )

    response = await auth_client.get("/api/v1/applications")
    assert response.status_code == 200

    listed = response.json()["data"][0]
    assert "iban" not in listed
    assert listed["has_sepa_mandate"] is True


async def test_the_detail_shows_them(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    application = await an_application(db_session, test_tenant, iban="DE02120300000000202051")

    response = await auth_client.get(f"/api/v1/applications/{application.id}")
    assert response.json()["data"]["iban"] == "DE02120300000000202051"


async def test_another_clubs_application_is_not_found(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    other = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other)
    await db_session.flush()
    foreign = await an_application(db_session, other)

    assert (await auth_client.get(f"/api/v1/applications/{foreign.id}")).status_code == 404
    assert (await auth_client.post(f"/api/v1/applications/{foreign.id}/accept")).status_code == 404


async def test_accepting_creates_the_member(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    application = await an_application(db_session, test_tenant)

    response = await auth_client.post(f"/api/v1/applications/{application.id}/accept")
    assert response.status_code == 200

    member = response.json()["data"]
    assert member["first_name"] == "Jonas"
    assert member["member_number"]

    await db_session.refresh(application)
    assert application.status == "accepted"
    assert application.member_id == uuid.UUID(member["id"])
    assert application.decided_at is not None


async def test_accepting_carries_over_the_requested_fee(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    fee = await a_fee(db_session, test_tenant, test_user)
    application = await an_application(db_session, test_tenant, fee_type_id=fee.id)

    response = await auth_client.post(f"/api/v1/applications/{application.id}/accept")
    member_id = uuid.UUID(response.json()["data"]["id"])

    assigned = (
        (await db_session.execute(select(MemberFee).where(MemberFee.member_id == member_id)))
        .scalars()
        .all()
    )
    assert len(assigned) == 1
    assert assigned[0].fee_type_id == fee.id


async def test_the_mandate_reference_is_assigned_on_acceptance(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """Before this moment there is no membership for it to name."""
    granted = date(2026, 8, 1)
    application = await an_application(
        db_session,
        test_tenant,
        iban="DE02120300000000202051",
        sepa_mandate_date=granted,
    )

    response = await auth_client.post(f"/api/v1/applications/{application.id}/accept")
    member_id = uuid.UUID(response.json()["data"]["id"])

    member = (await db_session.execute(select(Member).where(Member.id == member_id))).scalar_one()
    assert member.sepa_mandate_reference == f"M-{member.member_number}"
    assert member.sepa_mandate_date == granted


async def test_no_mandate_means_no_reference(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    application = await an_application(db_session, test_tenant)

    response = await auth_client.post(f"/api/v1/applications/{application.id}/accept")
    member_id = uuid.UUID(response.json()["data"]["id"])

    member = (await db_session.execute(select(Member).where(Member.id == member_id))).scalar_one()
    assert member.sepa_mandate_reference is None


async def test_rejecting_keeps_the_note_and_creates_nobody(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    application = await an_application(db_session, test_tenant)

    response = await auth_client.post(
        f"/api/v1/applications/{application.id}/reject",
        json={"note": "Wartet auf freien Standplatz"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "rejected"

    await db_session.refresh(application)
    assert application.decision_note == "Wartet auf freien Standplatz"
    assert application.member_id is None

    members = (
        (await db_session.execute(select(Member).where(Member.tenant_id == test_tenant.id)))
        .scalars()
        .all()
    )
    assert members == []


async def test_a_decided_application_cannot_be_decided_again(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """Two board members opening the same application must not admit twice."""
    application = await an_application(db_session, test_tenant)

    first = await auth_client.post(f"/api/v1/applications/{application.id}/accept")
    assert first.status_code == 200

    second = await auth_client.post(f"/api/v1/applications/{application.id}/accept")
    assert second.status_code == 409

    rejected = await auth_client.post(f"/api/v1/applications/{application.id}/reject", json={})
    assert rejected.status_code == 409

    members = (
        (await db_session.execute(select(Member).where(Member.tenant_id == test_tenant.id)))
        .scalars()
        .all()
    )
    assert len(members) == 1


async def test_filtering_by_status(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    pending = await an_application(db_session, test_tenant, first_name="Pending")
    decided = await an_application(db_session, test_tenant, first_name="Decided")
    await auth_client.post(f"/api/v1/applications/{decided.id}/reject", json={})

    response = await auth_client.get("/api/v1/applications", params={"status": "pending"})
    assert [a["id"] for a in response.json()["data"]] == [str(pending.id)]


async def test_the_club_opens_its_own_form(
    auth_client: AsyncClient, anon_client: AsyncClient, test_tenant: Tenant
) -> None:
    """The switch in the club settings is what the public endpoint reads."""
    assert (await anon_client.get(f"/join/{test_tenant.slug}")).status_code == 404

    opened = await auth_client.patch("/api/v1/club", json={"applications_enabled": True})
    assert opened.status_code == 200
    assert opened.json()["data"]["applications_enabled"] is True

    assert (await anon_client.get(f"/join/{test_tenant.slug}")).status_code == 200


async def test_accepting_carries_the_consents_to_the_member(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """The applicant answered on the form; the answers travel with them.

    Stamped with the moment the form was submitted, not the moment the board
    decided — a consent is dated when it was given.
    """
    application = await an_application(
        db_session, test_tenant, consent_photos=True, consent_newsletter=False
    )

    response = await auth_client.post(f"/api/v1/applications/{application.id}/accept")
    member_id = uuid.UUID(response.json()["data"]["id"])

    consents = (
        (
            await db_session.execute(
                select(MemberConsent).where(MemberConsent.member_id == member_id)
            )
        )
        .scalars()
        .all()
    )
    by_kind = {c.kind: c for c in consents}

    # All three, refusals included: asked-and-said-no is not the same state as
    # never-asked, and writing only the yesses would erase the difference.
    assert set(by_kind) == {"photos", "newsletter", "directory"}
    assert by_kind["photos"].granted is True
    assert by_kind["newsletter"].granted is False
    assert by_kind["photos"].source == "application"
    assert by_kind["photos"].recorded_at == application.privacy_accepted_at
