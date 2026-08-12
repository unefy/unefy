"""Who a round mail is actually going to.

The failure this guards against is silent: a selection that resolves to 143
people when it should be 155 sends a perfectly successful message to the wrong
list, and nobody notices until the twelve who were missed say they never heard
about the meeting.

So the rule is tested twice over — once as a pure function with no database in
the room, and once against real rows for each kind of selection.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent import MemberConsent
from app.models.due import Due, FeeType
from app.models.event import Event, EventRegistration
from app.models.function import Function, MemberFunction
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.message import AllMembers, Debtors, EventRegistrants, FunctionHolders
from app.services.recipients import RecipientResolver, decide, summarize

# --- The rule, without a database ---


def test_a_notice_reaches_a_member_who_refused_the_newsletter() -> None:
    """The invitation to the general meeting is an obligation, not a mailing.

    This is the whole reason a message carries a kind: without it the board
    has to choose between breaking the statutes and breaking the consent.
    """
    assert decide(email="a@example.org", consent=False, kind="notice") == ("pending", None)


def test_a_newsletter_does_not_reach_a_member_who_refused() -> None:
    assert decide(email="a@example.org", consent=False, kind="newsletter") == (
        "skipped",
        "refused",
    )


def test_never_asked_is_not_the_same_as_refused() -> None:
    """Both are skipped, and the club can act on exactly one of them."""
    assert decide(email="a@example.org", consent=None, kind="newsletter") == (
        "skipped",
        "not_asked",
    )


def test_a_granted_consent_lets_the_newsletter_through() -> None:
    assert decide(email="a@example.org", consent=True, kind="newsletter") == ("pending", None)


@pytest.mark.parametrize("email", [None, "", "   ", "kein-mail-adresse"])
def test_without_a_usable_address_nothing_can_be_sent(email: str | None) -> None:
    """Checked before consent: a missing address is not a consent problem, and
    naming it as one would send the board looking in the wrong place."""
    assert decide(email=email, consent=True, kind="notice") == ("skipped", "no_email")


def test_the_summary_keeps_the_two_reasons_apart() -> None:
    """ "28 were never asked" means ask them; "12 refused" means leave them be.
    Added together they are only "40 not reached"."""
    recipients = [
        _recipient("pending"),
        _recipient("skipped", "refused"),
        _recipient("skipped", "not_asked"),
        _recipient("skipped", "not_asked"),
        _recipient("skipped", "no_email"),
    ]

    summary = summarize(recipients)

    assert summary.total == 5
    assert summary.pending == 1
    assert summary.skipped_refused == 1
    assert summary.skipped_not_asked == 2
    assert summary.skipped_no_email == 1


def _recipient(status: str, reason: str | None = None):  # type: ignore[no-untyped-def]
    from app.services.recipients import ResolvedRecipient

    return ResolvedRecipient(
        member_id=uuid.uuid4(),
        first_name="Jonas",
        last_name="Weber",
        email="a@example.org",
        status=status,  # type: ignore[arg-type]
        reason=reason,  # type: ignore[arg-type]
    )


# --- Against real rows ---


async def a_member(
    db_session: AsyncSession,
    tenant: Tenant,
    user: User,
    *,
    number: str = "001",
    last_name: str = "Weber",
    email: str | None = "weber@example.org",
    status: str = "active",
) -> Member:
    member = Member(
        tenant_id=tenant.id,
        member_number=number,
        first_name="Jonas",
        last_name=last_name,
        email=email,
        joined_at=date(2020, 1, 1),
        status=status,
        created_by=user.id,
        updated_by=user.id,
    )
    db_session.add(member)
    await db_session.flush()
    return member


async def a_consent(
    db_session: AsyncSession, tenant: Tenant, member: Member, *, granted: bool
) -> None:
    db_session.add(
        MemberConsent(
            tenant_id=tenant.id,
            member_id=member.id,
            kind="newsletter",
            granted=granted,
            recorded_at=datetime.now(UTC),
            source="board",
        )
    )
    await db_session.flush()


async def test_all_members_means_the_active_ones(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """A former member is not written to — that is why people ask to be deleted."""
    await a_member(db_session, test_tenant, test_user, number="001", last_name="Aktiv")
    await a_member(db_session, test_tenant, test_user, number="002", last_name="Weg", status="left")

    resolved = await RecipientResolver(db_session, test_tenant.id).resolve(AllMembers(), "notice")

    assert [r.last_name for r in resolved] == ["Aktiv"]


async def test_another_clubs_members_are_never_in_the_list(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """The test that must not be missing."""
    other = Tenant(id=uuid.uuid4(), name="Nachbarverein", slug="nachbar-mail")
    db_session.add(other)
    await db_session.flush()
    await a_member(db_session, test_tenant, test_user, number="001", last_name="Eigen")
    await a_member(db_session, other, test_user, number="001", last_name="Fremd")

    resolved = await RecipientResolver(db_session, test_tenant.id).resolve(AllMembers(), "notice")

    assert [r.last_name for r in resolved] == ["Eigen"]


async def test_a_missing_address_is_reported_and_not_dropped(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """A list that silently holds only the reachable people cannot answer
    "why 143 and not 155"."""
    await a_member(db_session, test_tenant, test_user, number="001", last_name="Ohne", email=None)

    resolved = await RecipientResolver(db_session, test_tenant.id).resolve(AllMembers(), "notice")

    assert [(r.last_name, r.status, r.reason) for r in resolved] == [
        ("Ohne", "skipped", "no_email")
    ]


async def test_the_newsletter_filter_uses_the_newest_answer(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """The ledger is append-only, so "granted" can be yesterday's answer."""
    member = await a_member(db_session, test_tenant, test_user, number="001")
    db_session.add(
        MemberConsent(
            tenant_id=test_tenant.id,
            member_id=member.id,
            kind="newsletter",
            granted=True,
            recorded_at=datetime.now(UTC) - timedelta(days=30),
            source="application",
        )
    )
    await a_consent(db_session, test_tenant, member, granted=False)

    resolved = await RecipientResolver(db_session, test_tenant.id).resolve(
        AllMembers(), "newsletter"
    )

    assert [(r.status, r.reason) for r in resolved] == [("skipped", "refused")]


async def test_a_consent_to_something_else_does_not_open_the_newsletter(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """Photos and the directory are different questions."""
    member = await a_member(db_session, test_tenant, test_user, number="001")
    db_session.add(
        MemberConsent(
            tenant_id=test_tenant.id,
            member_id=member.id,
            kind="photos",
            granted=True,
            recorded_at=datetime.now(UTC),
            source="board",
        )
    )
    await db_session.flush()

    resolved = await RecipientResolver(db_session, test_tenant.id).resolve(
        AllMembers(), "newsletter"
    )

    assert [(r.status, r.reason) for r in resolved] == [("skipped", "not_asked")]


async def test_the_holders_of_an_office_are_the_ones_holding_it_today(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """A term that ended last year is not the board."""
    function = Function(
        tenant_id=test_tenant.id,
        name="Kassier",
        created_by=test_user.id,
        updated_by=test_user.id,
    )
    db_session.add(function)
    await db_session.flush()

    current = await a_member(db_session, test_tenant, test_user, number="001", last_name="Jetzt")
    former = await a_member(db_session, test_tenant, test_user, number="002", last_name="Damals")
    db_session.add_all(
        [
            MemberFunction(
                tenant_id=test_tenant.id,
                member_id=current.id,
                function_id=function.id,
                valid_from=date(2026, 1, 1),
                valid_to=None,
                created_by=test_user.id,
                updated_by=test_user.id,
            ),
            MemberFunction(
                tenant_id=test_tenant.id,
                member_id=former.id,
                function_id=function.id,
                valid_from=date(2023, 1, 1),
                valid_to=date(2025, 12, 31),
                created_by=test_user.id,
                updated_by=test_user.id,
            ),
        ]
    )
    await db_session.flush()

    resolved = await RecipientResolver(db_session, test_tenant.id).resolve(
        FunctionHolders(id=function.id), "notice", today=date(2026, 6, 1)
    )

    assert [r.last_name for r in resolved] == ["Jetzt"]


async def test_two_terms_of_the_same_office_are_still_one_mail(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    function = Function(
        tenant_id=test_tenant.id,
        name="Vorsitz",
        created_by=test_user.id,
        updated_by=test_user.id,
    )
    db_session.add(function)
    await db_session.flush()
    member = await a_member(db_session, test_tenant, test_user, number="001")
    db_session.add_all(
        [
            MemberFunction(
                tenant_id=test_tenant.id,
                member_id=member.id,
                function_id=function.id,
                valid_from=date(2024, 1, 1),
                valid_to=date(2026, 12, 31),
                created_by=test_user.id,
                updated_by=test_user.id,
            ),
            MemberFunction(
                tenant_id=test_tenant.id,
                member_id=member.id,
                function_id=function.id,
                valid_from=date(2026, 1, 1),
                valid_to=None,
                created_by=test_user.id,
                updated_by=test_user.id,
            ),
        ]
    )
    await db_session.flush()

    resolved = await RecipientResolver(db_session, test_tenant.id).resolve(
        FunctionHolders(id=function.id), "notice", today=date(2026, 6, 1)
    )

    assert len(resolved) == 1


async def test_the_registrants_of_an_event_without_the_waiting_list(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    event = Event(
        tenant_id=test_tenant.id,
        title="Vereinsausflug",
        starts_at=datetime.now(UTC) + timedelta(days=30),
        ends_at=datetime.now(UTC) + timedelta(days=30, hours=8),
        created_by=test_user.id,
        updated_by=test_user.id,
    )
    db_session.add(event)
    await db_session.flush()

    going = await a_member(db_session, test_tenant, test_user, number="001", last_name="Dabei")
    waiting = await a_member(db_session, test_tenant, test_user, number="002", last_name="Warte")
    db_session.add_all(
        [
            EventRegistration(
                tenant_id=test_tenant.id,
                event_id=event.id,
                member_id=going.id,
                status="registered",
                created_by=test_user.id,
                updated_by=test_user.id,
            ),
            EventRegistration(
                tenant_id=test_tenant.id,
                event_id=event.id,
                member_id=waiting.id,
                status="waitlist",
                created_by=test_user.id,
                updated_by=test_user.id,
            ),
        ]
    )
    await db_session.flush()

    resolver = RecipientResolver(db_session, test_tenant.id)
    without = await resolver.resolve(EventRegistrants(id=event.id), "notice")
    with_list = await resolver.resolve(
        EventRegistrants(id=event.id, include_waitlist=True), "notice"
    )

    assert [r.last_name for r in without] == ["Dabei"]
    # "The trip is cancelled" concerns the waiting list just as much.
    assert sorted(r.last_name for r in with_list) == ["Dabei", "Warte"]


async def test_the_debtors_of_a_year_are_those_with_something_open(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    fee_type = FeeType(
        tenant_id=test_tenant.id,
        name="Jahresbeitrag",
        amount=60,
        interval="yearly",
        created_by=test_user.id,
        updated_by=test_user.id,
    )
    db_session.add(fee_type)
    await db_session.flush()

    owing = await a_member(db_session, test_tenant, test_user, number="001", last_name="Offen")
    paid = await a_member(db_session, test_tenant, test_user, number="002", last_name="Bezahlt")
    other_year = await a_member(
        db_session, test_tenant, test_user, number="003", last_name="Vorjahr"
    )

    def due(member: Member, *, year: int, status: str) -> Due:
        return Due(
            tenant_id=test_tenant.id,
            member_id=member.id,
            fee_type_id=fee_type.id,
            fee_name="Jahresbeitrag",
            amount=60,
            period_start=date(year, 1, 1),
            period_end=date(year, 12, 31),
            due_date=date(year, 3, 1),
            status=status,
            created_by=test_user.id,
            updated_by=test_user.id,
        )

    db_session.add_all(
        [
            due(owing, year=2026, status="open"),
            due(paid, year=2026, status="paid"),
            due(other_year, year=2025, status="open"),
        ]
    )
    await db_session.flush()

    resolved = await RecipientResolver(db_session, test_tenant.id).resolve(
        Debtors(year=2026), "notice"
    )

    assert [r.last_name for r in resolved] == ["Offen"]


async def test_four_unpaid_quarters_are_one_recipient(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    fee_type = FeeType(
        tenant_id=test_tenant.id,
        name="Quartalsbeitrag",
        amount=15,
        interval="quarterly",
        created_by=test_user.id,
        updated_by=test_user.id,
    )
    db_session.add(fee_type)
    await db_session.flush()
    member = await a_member(db_session, test_tenant, test_user, number="001")
    for quarter in range(4):
        db_session.add(
            Due(
                tenant_id=test_tenant.id,
                member_id=member.id,
                fee_type_id=fee_type.id,
                fee_name="Quartalsbeitrag",
                amount=15,
                period_start=date(2026, 1 + quarter * 3, 1),
                period_end=date(2026, 3 + quarter * 3, 28),
                due_date=date(2026, 1 + quarter * 3, 15),
                status="open",
                created_by=test_user.id,
                updated_by=test_user.id,
            )
        )
    await db_session.flush()

    resolved = await RecipientResolver(db_session, test_tenant.id).resolve(
        Debtors(year=2026), "notice"
    )

    assert len(resolved) == 1
