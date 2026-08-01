"""Tests for club access: invitations, roles and revoking access.

This surface hands out permissions, so the tests focus on the ways it could
give away more than intended: a wrong role reaching the endpoints, an id from
another club, or a change that leaves the club without an owner.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import COOKIE_NAME, get_session_data
from app.models.invitation import Invitation
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from app.services.club_access import ClubAccessService, _hash

BASE = "/api/v1/club/access"

# Every club-access route, so a route added without the role guard shows up
# here rather than silently shipping open.
GUARDED_ENDPOINTS = [
    ("GET", BASE),
    ("POST", f"{BASE}/invitations"),
    ("DELETE", f"{BASE}/invitations/{uuid.uuid4()}"),
    ("PATCH", f"{BASE}/members/{uuid.uuid4()}"),
    ("PATCH", f"{BASE}/members/{uuid.uuid4()}/active"),
]


async def _invite(client: AsyncClient, email: str, role: str = "member"):  # type: ignore[no-untyped-def]
    return await client.post(f"{BASE}/invitations", json={"email": email, "role": role})


@pytest.fixture
async def other_tenant(db_session: AsyncSession) -> Tenant:
    tenant = Tenant(name="Fremdverein", slug=f"other-{uuid.uuid4().hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()
    return tenant


# --- Guard ---


@pytest.mark.parametrize(("method", "path"), GUARDED_ENDPOINTS)
async def test_endpoints_reject_anonymous(client: AsyncClient, method: str, path: str) -> None:
    resp = await client.request(method, path, json={})
    assert resp.status_code == 403, resp.text


async def test_endpoints_reject_ordinary_member(
    db_session: AsyncSession, fake_redis, test_tenant: Tenant
) -> None:  # type: ignore[no-untyped-def]
    """A plain member must not be able to hand out access."""
    from tests.test_admin import _session_client

    user = User(email="plain@example.com", name="Plain", email_verified=True)
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        TenantMembership(
            id=uuid.uuid4(),
            user_id=user.id,
            tenant_id=test_tenant.id,
            role="member",
            is_active=True,
        )
    )
    await db_session.flush()

    async for member_client in _session_client(
        db_session, fake_redis, user.id, test_tenant.id, "member"
    ):
        resp = await member_client.get(BASE)
        assert resp.status_code == 403, resp.text


# --- Listing ---


async def test_list_shows_members_and_open_invitations(
    auth_client: AsyncClient, test_user: User
) -> None:
    await _invite(auth_client, "pending@example.com", "board")

    resp = await auth_client.get(BASE)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert any(m["email"] == test_user.email for m in data["members"])
    assert [i["email"] for i in data["invitations"]] == ["pending@example.com"]
    assert data["invitations"][0]["role"] == "board"


async def test_revoked_invitation_disappears_from_the_list(
    auth_client: AsyncClient,
) -> None:
    created = await _invite(auth_client, "gone@example.com")
    invitation_id = created.json()["data"]["id"]

    resp = await auth_client.delete(f"{BASE}/invitations/{invitation_id}")
    assert resp.status_code == 204, resp.text

    listing = await auth_client.get(BASE)
    assert listing.json()["data"]["invitations"] == []


# --- Inviting ---


async def test_invite_stores_token_hashed_only(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A database dump must not yield working invitation links."""
    await _invite(auth_client, "hashed@example.com")

    invitation = (
        await db_session.execute(select(Invitation).where(Invitation.email == "hashed@example.com"))
    ).scalar_one()

    # 64 hex chars = SHA-256, and nothing that looks like a urlsafe token.
    assert len(invitation.token_hash) == 64
    assert invitation.accepted_at is None


async def test_invite_rejects_someone_who_already_has_access(
    auth_client: AsyncClient, test_user: User
) -> None:
    resp = await _invite(auth_client, test_user.email)
    assert resp.status_code == 409, resp.text


async def test_invite_rejects_a_second_open_invitation(
    auth_client: AsyncClient,
) -> None:
    assert (await _invite(auth_client, "twice@example.com")).status_code == 201
    assert (await _invite(auth_client, "twice@example.com")).status_code == 409


async def test_invite_rejects_unknown_role(auth_client: AsyncClient) -> None:
    resp = await _invite(auth_client, "role@example.com", "superuser")
    assert resp.status_code == 422, resp.text


async def test_invite_normalizes_the_address(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Casing must not let the same mailbox be invited twice."""
    await _invite(auth_client, "MiXeD@Example.COM")
    assert (await _invite(auth_client, "mixed@example.com")).status_code == 409


# --- Tenant isolation ---


async def test_cannot_revoke_an_invitation_of_another_club(
    auth_client: AsyncClient, db_session: AsyncSession, other_tenant: Tenant
) -> None:
    foreign = Invitation(
        tenant_id=other_tenant.id,
        email="foreign@example.com",
        role="member",
        token_hash=_hash("foreign-token"),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(foreign)
    await db_session.flush()

    resp = await auth_client.delete(f"{BASE}/invitations/{foreign.id}")
    assert resp.status_code == 404, resp.text

    await db_session.refresh(foreign)
    assert foreign.revoked_at is None


async def test_cannot_change_a_membership_of_another_club(
    auth_client: AsyncClient, db_session: AsyncSession, other_tenant: Tenant
) -> None:
    outsider = User(email="outsider@example.com", name="Outsider", email_verified=True)
    db_session.add(outsider)
    await db_session.flush()
    db_session.add(
        TenantMembership(
            id=uuid.uuid4(),
            user_id=outsider.id,
            tenant_id=other_tenant.id,
            role="member",
            is_active=True,
        )
    )
    await db_session.flush()

    resp = await auth_client.patch(f"{BASE}/members/{outsider.id}", json={"role": "owner"})
    assert resp.status_code == 404, resp.text


# --- Last owner ---


async def test_last_owner_cannot_be_demoted(auth_client: AsyncClient, test_user: User) -> None:
    """Otherwise the club loses the ability to administer itself."""
    resp = await auth_client.patch(f"{BASE}/members/{test_user.id}", json={"role": "member"})
    assert resp.status_code == 409, resp.text


async def test_last_owner_cannot_be_deactivated(auth_client: AsyncClient, test_user: User) -> None:
    resp = await auth_client.patch(
        f"{BASE}/members/{test_user.id}/active", json={"is_active": False}
    )
    assert resp.status_code == 409, resp.text


async def test_owner_can_be_demoted_once_a_second_owner_exists(
    auth_client: AsyncClient, db_session: AsyncSession, test_user: User, test_tenant: Tenant
) -> None:
    second = User(email="second@example.com", name="Second", email_verified=True)
    db_session.add(second)
    await db_session.flush()
    db_session.add(
        TenantMembership(
            id=uuid.uuid4(),
            user_id=second.id,
            tenant_id=test_tenant.id,
            role="owner",
            is_active=True,
        )
    )
    await db_session.flush()

    resp = await auth_client.patch(f"{BASE}/members/{test_user.id}", json={"role": "admin"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["role"] == "admin"


# --- Accepting ---


async def _issue(
    session: AsyncSession, tenant_id: uuid.UUID, email: str, role: str = "member"
) -> str:
    token = "test-token-" + uuid.uuid4().hex
    session.add(
        Invitation(
            tenant_id=tenant_id,
            email=email,
            role=role,
            token_hash=_hash(token),
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
    )
    await session.flush()
    return token


async def test_accept_creates_account_and_membership(
    client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    token = await _issue(db_session, test_tenant.id, "joiner@example.com", "board")

    resp = await client.get(f"/api/v1/auth/invitation/accept?token={token}")
    assert resp.status_code == 302, resp.text

    user = (
        await db_session.execute(select(User).where(User.email == "joiner@example.com"))
    ).scalar_one()
    # The link arrived in that mailbox, which is the proof.
    assert user.email_verified is True

    membership = (
        await db_session.execute(
            select(TenantMembership)
            .where(TenantMembership.user_id == user.id)
            .where(TenantMembership.tenant_id == test_tenant.id)
        )
    ).scalar_one()
    assert membership.role == "board"
    assert membership.is_active is True

    data = await get_session_data(resp.cookies[COOKIE_NAME])
    assert data is not None
    assert data.tenant_id == test_tenant.id
    assert data.role == "board"


async def test_accept_works_exactly_once(
    client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    token = await _issue(db_session, test_tenant.id, "once@example.com")

    first = await client.get(f"/api/v1/auth/invitation/accept?token={token}")
    second = await client.get(f"/api/v1/auth/invitation/accept?token={token}")

    assert first.cookies.get(COOKIE_NAME) is not None
    assert second.cookies.get(COOKIE_NAME) is None
    assert "error=invitation_invalid" in second.headers["location"]


async def test_accept_rejects_expired_invitation(
    client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    token = "expired-" + uuid.uuid4().hex
    db_session.add(
        Invitation(
            tenant_id=test_tenant.id,
            email="late@example.com",
            role="member",
            token_hash=_hash(token),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    await db_session.flush()

    resp = await client.get(f"/api/v1/auth/invitation/accept?token={token}")
    assert "error=invitation_invalid" in resp.headers["location"]
    assert resp.cookies.get(COOKIE_NAME) is None


async def test_accept_rejects_revoked_invitation(
    client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """Withdrawing an invitation has to actually stop the link from working."""
    token = await _issue(db_session, test_tenant.id, "revoked@example.com")
    invitation = (
        await db_session.execute(select(Invitation).where(Invitation.token_hash == _hash(token)))
    ).scalar_one()
    invitation.revoked_at = datetime.now(UTC)
    await db_session.flush()

    resp = await client.get(f"/api/v1/auth/invitation/accept?token={token}")
    assert "error=invitation_invalid" in resp.headers["location"]
    assert resp.cookies.get(COOKIE_NAME) is None


async def test_accept_rejects_unknown_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/invitation/accept?token=nonsense")
    assert "error=invitation_invalid" in resp.headers["location"]
    assert resp.cookies.get(COOKIE_NAME) is None


async def test_accept_restores_access_for_a_deactivated_account(
    client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """Re-inviting someone who was switched off must bring them back."""
    user = User(email="back@example.com", name="Back", email_verified=True)
    db_session.add(user)
    await db_session.flush()
    membership = TenantMembership(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=test_tenant.id,
        role="member",
        is_active=False,
    )
    db_session.add(membership)
    await db_session.flush()

    token = await _issue(db_session, test_tenant.id, "back@example.com", "admin")
    await client.get(f"/api/v1/auth/invitation/accept?token={token}")

    await db_session.refresh(membership)
    assert membership.is_active is True
    assert membership.role == "admin"


# --- Service-level ---


async def test_service_rejects_role_outside_the_rbac_set(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """The route validates by pattern; the service must not rely on that."""
    from app.core.exceptions import ValidationError

    service = ClubAccessService(db_session)
    with pytest.raises(ValidationError):
        await service.set_role(test_tenant.id, test_user.id, "root")


# --- Invitations tied to a member record ---


@pytest.fixture
async def club_member(db_session: AsyncSession, test_tenant: Tenant):  # type: ignore[no-untyped-def]
    from app.models.member import Member

    member = Member(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        member_number="M-100",
        first_name="Erika",
        last_name="Mustermann",
        email="erika@example.com",
        status="active",
    )
    db_session.add(member)
    await db_session.flush()
    return member


async def test_invite_from_member_uses_the_record_address(
    auth_client: AsyncClient, db_session: AsyncSession, club_member
) -> None:  # type: ignore[no-untyped-def]
    """A client-supplied address must never override the member's own.

    Otherwise an invitation could bind a stranger's account to this member —
    and with it to their dues and personal data in self-service.
    """
    resp = await auth_client.post(
        f"{BASE}/invitations",
        json={
            "member_id": str(club_member.id),
            "email": "attacker@example.com",
            "role": "member",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["email"] == "erika@example.com"


async def test_accepting_links_the_member_record(
    auth_client: AsyncClient, client: AsyncClient, db_session: AsyncSession, club_member
) -> None:  # type: ignore[no-untyped-def]
    await auth_client.post(
        f"{BASE}/invitations",
        json={"member_id": str(club_member.id), "role": "member"},
    )
    invitation = (
        await db_session.execute(select(Invitation).where(Invitation.member_id == club_member.id))
    ).scalar_one()

    # The mailed token is not recoverable from the hash, so reissue one.
    token = "member-link-" + uuid.uuid4().hex
    invitation.token_hash = _hash(token)
    await db_session.flush()

    resp = await client.get(f"/api/v1/auth/invitation/accept?token={token}")
    assert resp.status_code == 302, resp.text

    await db_session.refresh(club_member)
    assert club_member.user_id is not None

    user = (
        await db_session.execute(select(User).where(User.id == club_member.user_id))
    ).scalar_one()
    assert user.email == "erika@example.com"


async def test_invite_rejects_member_without_email(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """Not every member has an address — that has to fail clearly."""
    from app.models.member import Member

    member = Member(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        member_number="M-101",
        first_name="Kind",
        last_name="OhneMail",
        status="active",
    )
    db_session.add(member)
    await db_session.flush()

    resp = await auth_client.post(
        f"{BASE}/invitations", json={"member_id": str(member.id), "role": "member"}
    )
    assert resp.status_code == 422, resp.text


async def test_invite_rejects_member_who_already_has_an_account(
    auth_client: AsyncClient, db_session: AsyncSession, club_member, test_user: User
) -> None:  # type: ignore[no-untyped-def]
    club_member.user_id = test_user.id
    await db_session.flush()

    resp = await auth_client.post(
        f"{BASE}/invitations", json={"member_id": str(club_member.id), "role": "member"}
    )
    assert resp.status_code == 409, resp.text


async def test_cannot_invite_a_member_of_another_club(
    auth_client: AsyncClient, db_session: AsyncSession, other_tenant: Tenant
) -> None:
    from app.models.member import Member

    foreign = Member(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        member_number="F-1",
        first_name="Fremd",
        last_name="Mitglied",
        email="fremd@example.com",
        status="active",
    )
    db_session.add(foreign)
    await db_session.flush()

    resp = await auth_client.post(
        f"{BASE}/invitations", json={"member_id": str(foreign.id), "role": "member"}
    )
    assert resp.status_code == 404, resp.text


async def test_invite_without_member_or_email_is_rejected(
    auth_client: AsyncClient,
) -> None:
    resp = await auth_client.post(f"{BASE}/invitations", json={"role": "member"})
    assert resp.status_code == 422, resp.text
