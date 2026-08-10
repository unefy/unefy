"""Consents: the ledger, what it changes, and the export it feeds."""

import json
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent import MemberConsent
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def a_member(db_session: AsyncSession, tenant: Tenant, user: User, **kw: object) -> Member:
    member = Member(
        tenant_id=tenant.id,
        member_number=str(kw.pop("member_number", "001")),
        first_name=str(kw.pop("first_name", "Jonas")),
        last_name=str(kw.pop("last_name", "Weber")),
        joined_at=date.today(),
        status="active",
        created_by=user.id,
        updated_by=user.id,
        **kw,
    )
    db_session.add(member)
    await db_session.flush()
    return member


async def a_consent(
    db_session: AsyncSession,
    tenant: Tenant,
    member: Member,
    *,
    kind: str = "directory",
    granted: bool = True,
    recorded_at: datetime | None = None,
    source: str = "board",
) -> MemberConsent:
    entry = MemberConsent(
        tenant_id=tenant.id,
        member_id=member.id,
        kind=kind,
        granted=granted,
        recorded_at=recorded_at or datetime.now(UTC),
        source=source,
    )
    db_session.add(entry)
    await db_session.flush()
    return entry


# --- The ledger ---


async def test_recording_a_consent_appends_rather_than_overwrites(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A consent you can edit proves nothing, which is why this table exists."""
    member = await a_member(db_session, test_tenant, test_user)

    for granted in (True, False, True):
        response = await auth_client.post(
            f"/api/v1/members/{member.id}/consents",
            json={"kind": "newsletter", "granted": granted},
        )
        assert response.status_code == 201

    rows = (
        (
            await db_session.execute(
                select(MemberConsent).where(MemberConsent.member_id == member.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 3
    assert sorted(r.granted for r in rows) == [False, True, True]


async def test_the_current_answer_is_the_newest_one(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    member = await a_member(db_session, test_tenant, test_user)
    now = datetime.now(UTC)
    await a_consent(db_session, test_tenant, member, kind="photos", granted=True, recorded_at=now)
    await a_consent(
        db_session,
        test_tenant,
        member,
        kind="photos",
        granted=False,
        recorded_at=now + timedelta(days=1),
    )

    response = await auth_client.get(f"/api/v1/members/{member.id}/consents")
    assert response.status_code == 200

    current = {c["kind"]: c for c in response.json()["data"]["current"]}
    assert current["photos"]["granted"] is False
    assert len(response.json()["data"]["history"]) == 2


async def test_never_asked_is_not_the_same_as_refused(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """Three states, and collapsing them into a boolean loses the one that
    matters: whether the club ever put the question."""
    member = await a_member(db_session, test_tenant, test_user)
    await a_consent(db_session, test_tenant, member, kind="photos", granted=False)

    response = await auth_client.get(f"/api/v1/members/{member.id}/consents")
    current = {c["kind"]: c for c in response.json()["data"]["current"]}

    assert current["photos"]["granted"] is False
    assert current["newsletter"]["granted"] is None
    assert current["newsletter"]["since"] is None


async def test_a_member_records_their_own_withdrawal(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """Withdrawing must be no harder than consenting — same call, other value."""
    member = await a_member(db_session, test_tenant, test_user, user_id=test_user.id)
    await a_consent(db_session, test_tenant, member, kind="newsletter", granted=True)

    response = await auth_client.post(
        "/api/v1/members/me/consents", json={"kind": "newsletter", "granted": False}
    )
    assert response.status_code == 201
    assert response.json()["data"]["source"] == "self"

    own = await auth_client.get("/api/v1/members/me/consents")
    current = {c["kind"]: c for c in own.json()["data"]["current"]}
    assert current["newsletter"]["granted"] is False


async def test_a_member_cannot_backdate_their_own_answer(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The ledger records history; it is not a place to write it."""
    await a_member(db_session, test_tenant, test_user, user_id=test_user.id)

    response = await auth_client.post(
        "/api/v1/members/me/consents",
        json={
            "kind": "photos",
            "granted": True,
            "recorded_at": "2020-01-01T00:00:00Z",
        },
    )
    assert response.status_code == 201
    assert response.json()["data"]["recorded_at"][:4] != "2020"


async def test_the_board_may_backdate_a_paper_form(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A form that arrives three weeks late was signed when it was signed."""
    member = await a_member(db_session, test_tenant, test_user)

    response = await auth_client.post(
        f"/api/v1/members/{member.id}/consents",
        json={
            "kind": "photos",
            "granted": True,
            "recorded_at": "2026-07-01T10:00:00Z",
            "note": "Papierformular",
        },
    )
    assert response.status_code == 201
    assert response.json()["data"]["recorded_at"].startswith("2026-07-01")


async def test_an_unknown_consent_kind_is_refused(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    member = await a_member(db_session, test_tenant, test_user)

    response = await auth_client.post(
        f"/api/v1/members/{member.id}/consents",
        json={"kind": "whatever", "granted": True},
    )
    assert response.status_code == 422


async def test_another_clubs_member_is_not_found(
    auth_client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    other = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other)
    await db_session.flush()
    foreign = await a_member(db_session, other, test_user)

    assert (await auth_client.get(f"/api/v1/members/{foreign.id}/consents")).status_code == 404
    assert (
        await auth_client.post(
            f"/api/v1/members/{foreign.id}/consents",
            json={"kind": "photos", "granted": True},
        )
    ).status_code == 404


async def test_consents_need_a_signed_in_caller(anon_client: AsyncClient) -> None:
    assert (await anon_client.get("/api/v1/members/me/consents")).status_code == 403


# --- What the consent actually changes ---


async def test_the_directory_leaves_out_a_member_who_refused(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """Without this the consent is decoration: asked, stored, ignored."""
    listed = await a_member(db_session, test_tenant, test_user, member_number="001")
    hidden = await a_member(
        db_session,
        test_tenant,
        test_user,
        member_number="002",
        first_name="Nina",
        last_name="Roth",
    )
    await a_consent(db_session, test_tenant, hidden, kind="directory", granted=False)

    response = await auth_client.get("/api/v1/members/directory")
    assert response.status_code == 200

    ids = [entry["id"] for entry in response.json()["data"]]
    assert str(listed.id) in ids
    assert str(hidden.id) not in ids
    assert response.json()["meta"]["total"] == 1


async def test_a_member_never_asked_stays_in_the_directory(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """Otherwise switching this on would empty every existing club's list."""
    member = await a_member(db_session, test_tenant, test_user)

    response = await auth_client.get("/api/v1/members/directory")
    assert [e["id"] for e in response.json()["data"]] == [str(member.id)]


async def test_withdrawing_removes_the_member_again(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The newest answer wins, in both directions."""
    member = await a_member(db_session, test_tenant, test_user)
    now = datetime.now(UTC)
    await a_consent(
        db_session, test_tenant, member, kind="directory", granted=False, recorded_at=now
    )
    await a_consent(
        db_session,
        test_tenant,
        member,
        kind="directory",
        granted=True,
        recorded_at=now + timedelta(minutes=1),
    )

    listed = await auth_client.get("/api/v1/members/directory")
    assert [e["id"] for e in listed.json()["data"]] == [str(member.id)]

    await a_consent(
        db_session,
        test_tenant,
        member,
        kind="directory",
        granted=False,
        recorded_at=now + timedelta(minutes=2),
    )

    gone = await auth_client.get("/api/v1/members/directory")
    assert gone.json()["data"] == []


async def test_a_refusal_in_another_club_does_not_hide_the_member_here(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    member = await a_member(db_session, test_tenant, test_user)

    other = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other)
    await db_session.flush()
    db_session.add(
        MemberConsent(
            tenant_id=other.id,
            member_id=member.id,
            kind="directory",
            granted=False,
            recorded_at=datetime.now(UTC),
            source="board",
        )
    )
    await db_session.flush()

    response = await auth_client.get("/api/v1/members/directory")
    assert [e["id"] for e in response.json()["data"]] == [str(member.id)]


# --- Art. 15 export ---


async def test_the_export_bundles_the_member_and_their_consents(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    member = await a_member(db_session, test_tenant, test_user, user_id=test_user.id)
    await a_consent(db_session, test_tenant, member, kind="photos", granted=True)

    response = await auth_client.get("/api/v1/members/me/export")
    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment")
    # A copy of somebody's personal data has no business in a cache.
    assert response.headers["cache-control"] == "no-store"

    payload = json.loads(response.content)
    assert payload["member"]["member_number"] == member.member_number
    assert payload["export"]["controller"] == test_tenant.name
    assert [c["kind"] for c in payload["consents"]] == ["photos"]
    # Every section is present even when empty, so a reader can tell "none"
    # from "not asked for".
    for section in ("federations", "functions", "fees", "dues", "attendance"):
        assert section in payload


async def test_the_export_stops_at_the_club_boundary(
    auth_client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    other = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other)
    await db_session.flush()
    foreign = await a_member(db_session, other, test_user)

    response = await auth_client.get(f"/api/v1/members/{foreign.id}/export")
    assert response.status_code == 404


async def test_an_account_without_a_member_record_gets_a_clear_404(
    auth_client: AsyncClient,
) -> None:
    """A board member who administers a club they do not belong to."""
    assert (await auth_client.get("/api/v1/members/me/export")).status_code == 404
    assert (await auth_client.get("/api/v1/members/me/consents")).status_code == 404
