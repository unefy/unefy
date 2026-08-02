"""Member self-service endpoints.

The rest of the API is administrative: 43 endpoints require board or above.
These four are the ones a plain member may call, so the tests here are less
about happy paths and more about the boundary — a member must reach exactly
their own data and nothing else, and must not gain anything beyond it.
"""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models.due import Due, FeeType
from app.models.event import Event
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User


async def _add_member(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    member_number: str,
    user_id: uuid.UUID | None = None,
    first_name: str = "Alice",
    last_name: str = "Example",
) -> Member:
    member = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_number=member_number,
        first_name=first_name,
        last_name=last_name,
        joined_at=date(2024, 1, 1),
        status="active",
        user_id=user_id,
    )
    session.add(member)
    await session.flush()
    return member


async def _add_due(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    member_id: uuid.UUID,
    *,
    amount: str = "120.00",
) -> Due:
    # Unique per call: fee_types is constrained on (tenant_id, name).
    fee_type = FeeType(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=f"Beitrag {uuid.uuid4().hex[:8]}",
        amount=Decimal(amount),
    )
    session.add(fee_type)
    await session.flush()

    due = Due(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_id=member_id,
        fee_type_id=fee_type.id,
        fee_name=fee_type.name,
        amount=Decimal(amount),
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        due_date=date(2025, 1, 31),
        status="open",
    )
    session.add(due)
    await session.flush()
    return due


async def _add_event(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    max_participants: int | None = None,
) -> Event:
    event = Event(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        title="Vereinsabend",
        event_type="other",
        starts_at=datetime(2026, 9, 1, 19, 0, tzinfo=UTC),
        registration_required=True,
        max_participants=max_participants,
    )
    session.add(event)
    await session.flush()
    return event


async def _client_as(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str = "member",
) -> AsyncClient:
    """A client whose session carries an explicit role — "member" by default."""
    import app.redis as redis_module
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession]:  # type: ignore[type-arg]
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    redis_module._redis_client = fake_redis

    token = uuid.uuid4().hex
    await fake_redis.set(
        f"session:{token}",
        json.dumps({"user_id": str(user_id), "tenant_id": str(tenant_id), "role": role}),
        ex=604800,
    )

    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": token},
    )


async def test_members_me_returns_own_record_for_plain_member(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """A member with role "member" can read their own record."""
    await _add_member(db_session, test_tenant.id, member_number="001", user_id=test_user.id)
    await _add_member(db_session, test_tenant.id, member_number="002", first_name="Someone")

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get("/api/v1/members/me")

    assert response.status_code == 200
    assert response.json()["data"]["member_number"] == "001"


async def test_members_me_is_404_without_a_linked_record(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """A board account that is not itself a member is a normal state, not a crash."""
    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id, role="board")
    async with client as ac:
        response = await ac.get("/api/v1/members/me")

    assert response.status_code == 404


async def test_members_me_does_not_cross_tenants(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """The same user linked in another tenant must not leak that record."""
    foreign = Tenant(id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    db_session.add(foreign)
    await db_session.flush()
    await _add_member(db_session, foreign.id, member_number="999", user_id=test_user.id)

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get("/api/v1/members/me")

    assert response.status_code == 404


async def test_a_plain_member_still_cannot_list_all_members(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """Self-service must not widen the administrative surface."""
    await _add_member(db_session, test_tenant.id, member_number="001", user_id=test_user.id)

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get("/api/v1/members")

    assert response.status_code == 403


async def test_dues_me_returns_only_the_callers_dues(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """The member_id comes from the session, so another member's dues stay hidden."""
    mine = await _add_member(
        db_session, test_tenant.id, member_number="001", user_id=test_user.id
    )
    theirs = await _add_member(db_session, test_tenant.id, member_number="002")
    await _add_due(db_session, test_tenant.id, mine.id, amount="120.00")
    await _add_due(db_session, test_tenant.id, theirs.id, amount="999.00")

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get("/api/v1/dues/me")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["amount"] == "120.00"


async def test_a_member_can_register_and_unregister_themselves(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """The whole point of the member app: signing yourself up for an event."""
    await _add_member(db_session, test_tenant.id, member_number="001", user_id=test_user.id)
    event = await _add_event(db_session, test_tenant.id, max_participants=10)

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        created = await ac.post(f"/api/v1/events/{event.id}/registrations/me")
        assert created.status_code == 201

        removed = await ac.delete(f"/api/v1/events/{event.id}/registrations/me")
        assert removed.status_code == 204

        # Cancelling twice is a 404, not a silent success.
        again = await ac.delete(f"/api/v1/events/{event.id}/registrations/me")
        assert again.status_code == 404


async def test_self_registration_requires_a_linked_member_record(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """An account with no member row cannot register — and gets a clear 404."""
    event = await _add_event(db_session, test_tenant.id)

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.post(f"/api/v1/events/{event.id}/registrations/me")

    assert response.status_code == 404


async def test_club_exposes_sports_and_the_modules_they_activate(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """Modules are the union over the club's sports, not a per-club setting."""
    from app.models.sport import Sport
    from app.models.tenant_sport import TenantSport

    shooting = Sport(
        id=uuid.uuid4(),
        key=f"shooting-{uuid.uuid4().hex[:8]}",
        name="Schießsport",
        modules=["shooting"],
    )
    gymnastics = Sport(
        id=uuid.uuid4(),
        key=f"gym-{uuid.uuid4().hex[:8]}",
        name="Turnen",
        modules=[],
    )
    db_session.add_all([shooting, gymnastics])
    await db_session.flush()
    db_session.add_all(
        [
            TenantSport(tenant_id=test_tenant.id, sport_id=gymnastics.id, is_primary=True),
            TenantSport(tenant_id=test_tenant.id, sport_id=shooting.id),
        ]
    )
    await db_session.flush()

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get("/api/v1/club")

    assert response.status_code == 200
    data = response.json()["data"]
    # A multi-sport club gets the shooting module through its section.
    assert data["modules"] == ["shooting"]
    # Primary first, so a UI that shows one sport shows the right one.
    assert data["sports"][0]["name"] == "Turnen"
    assert data["sports"][0]["is_primary"] is True


async def test_a_club_without_sports_has_no_modules(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """The default is generic: nothing sport-specific is shown until assigned."""
    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get("/api/v1/club")

    assert response.status_code == 200
    assert response.json()["data"]["modules"] == []
    assert response.json()["data"]["sports"] == []


async def test_setting_club_sports_requires_admin_and_rejects_unknown_ids(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """Configuration stays administrative, and a bad id writes nothing."""
    member_client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with member_client as ac:
        forbidden = await ac.put("/api/v1/club/sports", json={"sport_ids": []})
    assert forbidden.status_code == 403

    admin_client = await _client_as(
        db_session, fake_redis, test_user.id, test_tenant.id, role="admin"
    )
    async with admin_client as ac:
        unknown = await ac.put(
            "/api/v1/club/sports", json={"sport_ids": [str(uuid.uuid4())]}
        )
    assert unknown.status_code == 404


async def test_directory_is_open_to_members_but_narrow(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """A member sees who else is in the club — and nothing sensitive about them."""
    member = await _add_member(
        db_session, test_tenant.id, member_number="001", first_name="Klara"
    )
    member.email = "klara@example.com"
    member.iban = "DE02120300000000202051"
    member.city = "Tübingen"
    member.category = "Erwachsene"
    await db_session.flush()

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get("/api/v1/members/directory")

    assert response.status_code == 200
    entry = response.json()["data"][0]
    assert entry["first_name"] == "Klara"
    assert entry["category"] == "Erwachsene"
    # The whole point of the separate schema.
    for leaked in ("email", "iban", "city", "phone", "birthday", "member_number"):
        assert leaked not in entry


async def test_directory_only_lists_active_members(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """Former members are not part of "who is in the club"."""
    await _add_member(db_session, test_tenant.id, member_number="001", first_name="Aktiv")
    gone = await _add_member(
        db_session, test_tenant.id, member_number="002", first_name="Weg"
    )
    gone.status = "resigned"
    await db_session.flush()

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get("/api/v1/members/directory")

    names = [e["first_name"] for e in response.json()["data"]]
    assert names == ["Aktiv"]


async def test_directory_search_does_not_match_on_email(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """Otherwise the directory becomes an oracle for "is this address a member?"."""
    member = await _add_member(
        db_session, test_tenant.id, member_number="001", first_name="Klara"
    )
    member.email = "geheim@example.com"
    await db_session.flush()

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        by_email = await ac.get("/api/v1/members/directory", params={"search": "geheim"})
        by_name = await ac.get("/api/v1/members/directory", params={"search": "Klara"})

    assert by_email.json()["meta"]["total"] == 0
    assert by_name.json()["meta"]["total"] == 1


async def test_directory_does_not_cross_tenants(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """Tenant scoping holds on the member-facing path too."""
    foreign = Tenant(id=uuid.uuid4(), name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    db_session.add(foreign)
    await db_session.flush()
    await _add_member(db_session, foreign.id, member_number="999", first_name="Fremd")
    await _add_member(db_session, test_tenant.id, member_number="001", first_name="Eigen")

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get("/api/v1/members/directory")

    assert [e["first_name"] for e in response.json()["data"]] == ["Eigen"]


async def test_events_tell_the_caller_whether_they_are_registered(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """Without this flag the app cannot tell "register" from "cancel"."""
    await _add_member(db_session, test_tenant.id, member_number="001", user_id=test_user.id)
    joined = await _add_event(db_session, test_tenant.id, max_participants=10)
    other = await _add_event(db_session, test_tenant.id, max_participants=10)

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        assert (await ac.post(f"/api/v1/events/{joined.id}/registrations/me")).status_code == 201
        listing = await ac.get("/api/v1/events")

    flags = {e["id"]: e["is_registered"] for e in listing.json()["data"]}
    assert flags[str(joined.id)] is True
    assert flags[str(other.id)] is False


async def test_is_registered_is_false_without_a_member_record(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """A board account with no member row still gets a well-formed list."""
    await _add_event(db_session, test_tenant.id)

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id, role="board")
    async with client as ac:
        listing = await ac.get("/api/v1/events")

    assert listing.status_code == 200
    assert listing.json()["data"][0]["is_registered"] is False


async def test_a_member_may_read_competitions_but_not_change_them(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """The scoreboard is what a member cares about most; editing is not theirs."""
    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        listing = await ac.get("/api/v1/competitions")
        created = await ac.post(
            "/api/v1/competitions",
            json={"name": "Nicht erlaubt", "start_date": "2026-01-01"},
        )

    assert listing.status_code == 200
    assert created.status_code == 403


async def test_the_scoreboard_carries_member_names(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """A ranking of UUIDs answers no question — the name has to come with it."""
    from datetime import date as _date

    from app.models.competition import Competition, Entry
    from app.models.competition import Session as CompSession

    member = await _add_member(
        db_session, test_tenant.id, member_number="001", first_name="Klara", last_name="Ritter"
    )
    competition = Competition(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        name="Vereinsmeisterschaft",
        start_date=_date(2026, 3, 1),
        scoring_mode="highest_wins",
        scoring_unit="Ringe",
    )
    db_session.add(competition)
    await db_session.flush()
    comp_session = CompSession(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        competition_id=competition.id,
        name="Durchgang 1",
        date=_date(2026, 3, 7),
    )
    db_session.add(comp_session)
    await db_session.flush()
    db_session.add(
        Entry(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            session_id=comp_session.id,
            member_id=member.id,
            score_value=358.0,
            recorded_at=datetime(2026, 3, 7, 10, 0, tzinfo=UTC),
        )
    )
    await db_session.flush()

    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get(f"/api/v1/competitions/{competition.id}/scoreboard")

    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["member_name"] == "Klara Ritter"
    assert row["rank"] == 1
    assert response.json()["scoring_unit"] == "Ringe"
