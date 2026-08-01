"""Tests for the platform admin area and impersonation.

This is auth-critical surface: `require_platform_admin` deliberately bypasses
tenant isolation, so the tests below focus on who is refused, not just on the
happy path.
"""

import json
import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models.audit import AdminAuditLog
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User

# Every admin route, used to assert the guard is applied consistently rather
# than endpoint by endpoint — a new route added without the guard shows up here.
ADMIN_ENDPOINTS = [
    ("GET", "/api/v1/admin/tenants"),
    ("GET", f"/api/v1/admin/tenants/{uuid.uuid4()}"),
    ("GET", f"/api/v1/admin/tenants/{uuid.uuid4()}/users"),
    ("GET", f"/api/v1/admin/tenants/{uuid.uuid4()}/members"),
    ("GET", "/api/v1/admin/users"),
    ("GET", "/api/v1/admin/audit-log"),
]


async def _session_client(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    user_id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
    role: str | None = None,
) -> AsyncGenerator[AsyncClient]:  # type: ignore[type-arg]
    import app.redis as redis_module
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession]:  # type: ignore[type-arg]
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    original_redis = redis_module._redis_client
    redis_module._redis_client = fake_redis

    token = uuid.uuid4().hex
    await fake_redis.set(
        f"session:{token}",
        json.dumps(
            {
                "user_id": str(user_id),
                "tenant_id": str(tenant_id) if tenant_id else None,
                "role": role,
            }
        ),
        ex=604800,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": token},
    ) as ac:
        yield ac

    redis_module._redis_client = original_redis
    app.dependency_overrides.clear()


@pytest.fixture
async def superuser(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="platform-admin@example.com",
        name="Platform Admin",
        email_verified=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def superuser_client(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    superuser: User,
) -> AsyncGenerator[AsyncClient]:  # type: ignore[type-arg]
    async for c in _session_client(db_session, fake_redis, superuser.id):
        yield c


@pytest.fixture
async def club_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    """An ordinary user who owns `test_tenant` — the impersonation target."""
    user = User(
        id=uuid.uuid4(),
        email="club-owner@example.com",
        name="Club Owner",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        TenantMembership(
            id=uuid.uuid4(),
            user_id=user.id,
            tenant_id=test_tenant.id,
            role="owner",
            is_active=True,
        )
    )
    await db_session.flush()
    return user


# --- Guard ---


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
async def test_admin_endpoints_reject_anonymous(
    client: AsyncClient, method: str, path: str
) -> None:
    resp = await client.request(method, path)
    assert resp.status_code == 403, resp.text


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
async def test_admin_endpoints_reject_ordinary_user(
    auth_client: AsyncClient, method: str, path: str
) -> None:
    """A club owner is an admin *within* their club — never on the platform."""
    resp = await auth_client.request(method, path)
    assert resp.status_code == 403, resp.text


async def test_impersonate_rejects_ordinary_user(
    auth_client: AsyncClient, club_user: User, test_tenant: Tenant
) -> None:
    resp = await auth_client.post(
        "/api/v1/admin/impersonate",
        json={
            "user_id": str(club_user.id),
            "tenant_id": str(test_tenant.id),
            "reason": "should not work",
        },
    )
    assert resp.status_code == 403, resp.text


async def test_revoking_superuser_takes_effect_immediately(
    superuser_client: AsyncClient, superuser: User, db_session: AsyncSession
) -> None:
    """The flag is read per request, so revocation must not wait for expiry."""
    assert (await superuser_client.get("/api/v1/admin/tenants")).status_code == 200

    superuser.is_superuser = False
    await db_session.flush()

    assert (await superuser_client.get("/api/v1/admin/tenants")).status_code == 403


# --- Listings ---


async def test_list_tenants_includes_counts(
    superuser_client: AsyncClient, test_tenant: Tenant, club_user: User
) -> None:
    resp = await superuser_client.get("/api/v1/admin/tenants")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    entry = next(t for t in body["data"] if t["id"] == str(test_tenant.id))
    assert entry["name"] == "Test Club"
    assert entry["user_count"] == 1
    assert body["meta"]["total"] >= 1


async def test_list_users_exposes_superuser_flag(
    superuser_client: AsyncClient, superuser: User, club_user: User
) -> None:
    resp = await superuser_client.get("/api/v1/admin/users")
    assert resp.status_code == 200, resp.text
    by_email = {u["email"]: u for u in resp.json()["data"]}

    assert by_email[superuser.email]["is_superuser"] is True
    assert by_email[club_user.email]["is_superuser"] is False


async def test_list_users_search_filters(superuser_client: AsyncClient, club_user: User) -> None:
    resp = await superuser_client.get("/api/v1/admin/users", params={"search": "club-owner"})
    assert resp.status_code == 200, resp.text
    emails = [u["email"] for u in resp.json()["data"]]
    assert emails == [club_user.email]


async def test_get_user(superuser_client: AsyncClient, club_user: User) -> None:
    resp = await superuser_client.get(f"/api/v1/admin/users/{club_user.id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["email"] == club_user.email
    assert data["is_superuser"] is False


async def test_get_user_unknown_id(superuser_client: AsyncClient) -> None:
    resp = await superuser_client.get(f"/api/v1/admin/users/{uuid.uuid4()}")
    assert resp.status_code == 404, resp.text


async def test_get_user_rejects_ordinary_user(auth_client: AsyncClient, club_user: User) -> None:
    resp = await auth_client.get(f"/api/v1/admin/users/{club_user.id}")
    assert resp.status_code == 403, resp.text


async def test_get_tenant(
    superuser_client: AsyncClient, test_tenant: Tenant, club_user: User
) -> None:
    resp = await superuser_client.get(f"/api/v1/admin/tenants/{test_tenant.id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["name"] == test_tenant.name
    assert data["slug"] == test_tenant.slug
    assert data["user_count"] == 1
    assert data["member_count"] == 0


async def test_get_tenant_unknown_id(superuser_client: AsyncClient) -> None:
    resp = await superuser_client.get(f"/api/v1/admin/tenants/{uuid.uuid4()}")
    assert resp.status_code == 404, resp.text


async def test_list_tenant_users(
    superuser_client: AsyncClient, test_tenant: Tenant, club_user: User
) -> None:
    resp = await superuser_client.get(f"/api/v1/admin/tenants/{test_tenant.id}/users")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == [
        {
            "user_id": str(club_user.id),
            "name": club_user.name,
            "email": club_user.email,
            "role": "owner",
            "is_active": True,
        }
    ]


async def test_list_tenant_members_omits_personal_and_banking_data(
    superuser_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """Platform admins see that members exist — not the club's private records."""
    from datetime import date

    from app.models.member import Member

    db_session.add(
        Member(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            member_number="M-001",
            first_name="Erika",
            last_name="Mustermann",
            email="erika@example.com",
            birthday=date(1980, 5, 4),
            street="Musterweg 1",
            iban="DE02120300000000202051",
            bic="BYLADEM1001",
            notes="internal note",
            status="active",
        )
    )
    await db_session.flush()

    resp = await superuser_client.get(f"/api/v1/admin/tenants/{test_tenant.id}/members")
    assert resp.status_code == 200, resp.text
    entries = resp.json()["data"]
    assert len(entries) == 1

    entry = entries[0]
    assert entry["last_name"] == "Mustermann"
    assert entry["member_number"] == "M-001"
    assert entry["status"] == "active"
    assert entry["has_account"] is False

    leaked = {"iban", "bic", "sepa_mandate_reference", "birthday", "street", "notes", "email"}
    assert leaked.isdisjoint(entry.keys()), f"leaked fields: {leaked & entry.keys()}"


async def test_list_tenant_members_hides_soft_deleted(
    superuser_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    from datetime import UTC, datetime

    from app.models.member import Member

    db_session.add(
        Member(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            member_number="M-002",
            first_name="Max",
            last_name="Weg",
            status="active",
            deleted_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    resp = await superuser_client.get(f"/api/v1/admin/tenants/{test_tenant.id}/members")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == []


async def test_tenant_detail_rejects_ordinary_user(
    auth_client: AsyncClient, test_tenant: Tenant
) -> None:
    """A club owner cannot read their own club through the platform admin API."""
    for path in ("", "/users", "/members"):
        resp = await auth_client.get(f"/api/v1/admin/tenants/{test_tenant.id}{path}")
        assert resp.status_code == 403, resp.text


async def test_list_user_memberships(
    superuser_client: AsyncClient, club_user: User, test_tenant: Tenant
) -> None:
    resp = await superuser_client.get(f"/api/v1/admin/users/{club_user.id}/memberships")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == [
        {
            "tenant_id": str(test_tenant.id),
            "tenant_name": test_tenant.name,
            "role": "owner",
            "is_active": True,
        }
    ]


# --- Impersonation ---


async def test_impersonate_happy_path(
    superuser_client: AsyncClient,
    superuser: User,
    club_user: User,
    test_tenant: Tenant,
) -> None:
    resp = await superuser_client.post(
        "/api/v1/admin/impersonate",
        json={
            "user_id": str(club_user.id),
            "tenant_id": str(test_tenant.id),
            "reason": "Investigating a dues export bug",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["user_email"] == club_user.email
    assert data["tenant_id"] == str(test_tenant.id)
    assert data["role"] == "owner"
    assert data["expires_in"] == 3600

    # The client now carries the impersonation cookie, so /me reflects the
    # impersonated identity while naming the admin behind it.
    me = (await superuser_client.get("/api/v1/auth/me")).json()["data"]
    assert me["user"]["email"] == club_user.email
    assert me["tenant_id"] == str(test_tenant.id)
    assert me["impersonator"]["email"] == superuser.email


async def test_impersonated_session_cannot_reach_admin_area(
    superuser_client: AsyncClient, club_user: User, test_tenant: Tenant
) -> None:
    """The escalation path that would make impersonation a privilege loophole."""
    await superuser_client.post(
        "/api/v1/admin/impersonate",
        json={
            "user_id": str(club_user.id),
            "tenant_id": str(test_tenant.id),
            "reason": "checking admin access is blocked",
        },
    )
    assert (await superuser_client.get("/api/v1/admin/tenants")).status_code == 403


async def test_cannot_impersonate_another_platform_admin(
    superuser_client: AsyncClient, db_session: AsyncSession
) -> None:
    other = User(
        id=uuid.uuid4(),
        email="other-admin@example.com",
        name="Other Admin",
        email_verified=True,
        is_superuser=True,
    )
    db_session.add(other)
    await db_session.flush()

    resp = await superuser_client.post(
        "/api/v1/admin/impersonate",
        json={"user_id": str(other.id), "reason": "should be refused"},
    )
    assert resp.status_code == 403, resp.text


async def test_cannot_impersonate_self(superuser_client: AsyncClient, superuser: User) -> None:
    resp = await superuser_client.post(
        "/api/v1/admin/impersonate",
        json={"user_id": str(superuser.id), "reason": "should be refused"},
    )
    assert resp.status_code == 422, resp.text


async def test_impersonate_requires_tenant_when_user_has_clubs(
    superuser_client: AsyncClient, club_user: User
) -> None:
    resp = await superuser_client.post(
        "/api/v1/admin/impersonate",
        json={"user_id": str(club_user.id), "reason": "no tenant given"},
    )
    assert resp.status_code == 422, resp.text


async def test_impersonate_rejects_tenant_without_membership(
    superuser_client: AsyncClient, club_user: User
) -> None:
    resp = await superuser_client.post(
        "/api/v1/admin/impersonate",
        json={
            "user_id": str(club_user.id),
            "tenant_id": str(uuid.uuid4()),
            "reason": "wrong club",
        },
    )
    assert resp.status_code == 404, resp.text


async def test_impersonate_rejects_unknown_user(superuser_client: AsyncClient) -> None:
    resp = await superuser_client.post(
        "/api/v1/admin/impersonate",
        json={"user_id": str(uuid.uuid4()), "reason": "no such user"},
    )
    assert resp.status_code == 404, resp.text


async def test_impersonate_requires_reason(
    superuser_client: AsyncClient, club_user: User, test_tenant: Tenant
) -> None:
    """The reason is what makes an audit entry useful months later."""
    resp = await superuser_client.post(
        "/api/v1/admin/impersonate",
        json={"user_id": str(club_user.id), "tenant_id": str(test_tenant.id)},
    )
    assert resp.status_code == 422, resp.text


async def test_stop_restores_original_admin_session(
    superuser_client: AsyncClient,
    superuser: User,
    club_user: User,
    test_tenant: Tenant,
) -> None:
    await superuser_client.post(
        "/api/v1/admin/impersonate",
        json={
            "user_id": str(club_user.id),
            "tenant_id": str(test_tenant.id),
            "reason": "round trip",
        },
    )
    assert (await superuser_client.get("/api/v1/auth/me")).json()["data"]["user"][
        "email"
    ] == club_user.email

    resp = await superuser_client.post("/api/v1/admin/impersonate/stop")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["restored"] is True

    me = (await superuser_client.get("/api/v1/auth/me")).json()["data"]
    assert me["user"]["email"] == superuser.email
    assert me["impersonator"] is None
    assert me["is_superuser"] is True

    # Admin powers are back.
    assert (await superuser_client.get("/api/v1/admin/tenants")).status_code == 200


async def test_stop_rejects_normal_session(auth_client: AsyncClient) -> None:
    resp = await auth_client.post("/api/v1/admin/impersonate/stop")
    assert resp.status_code == 422, resp.text


async def test_stop_without_session_is_rejected(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/admin/impersonate/stop")
    assert resp.status_code == 403, resp.text


# --- Audit ---


async def test_impersonation_is_audited_with_attribution(
    superuser_client: AsyncClient,
    superuser: User,
    club_user: User,
    test_tenant: Tenant,
    db_session: AsyncSession,
) -> None:
    await superuser_client.post(
        "/api/v1/admin/impersonate",
        json={
            "user_id": str(club_user.id),
            "tenant_id": str(test_tenant.id),
            "reason": "Investigating a dues export bug",
        },
    )
    await superuser_client.post("/api/v1/admin/impersonate/stop")

    entries = (
        (await db_session.execute(select(AdminAuditLog).order_by(AdminAuditLog.created_at.asc())))
        .scalars()
        .all()
    )
    actions = [e.action for e in entries]
    assert "impersonation.start" in actions
    assert "impersonation.stop" in actions

    start = next(e for e in entries if e.action == "impersonation.start")
    assert start.actor_user_id == superuser.id
    assert start.impersonator_id is None
    assert start.target_id == club_user.id
    assert start.tenant_id == test_tenant.id
    assert start.payload is not None
    assert start.payload["reason"] == "Investigating a dues export bug"

    # The stop call runs *as* the impersonated user, so the log must name both
    # identities — otherwise the trail loses who was actually at the keyboard.
    stop = next(e for e in entries if e.action == "impersonation.stop")
    assert stop.actor_user_id == club_user.id
    assert stop.impersonator_id == superuser.id


async def test_audit_log_endpoint_lists_entries(
    superuser_client: AsyncClient,
    superuser: User,
    club_user: User,
    test_tenant: Tenant,
) -> None:
    await superuser_client.post(
        "/api/v1/admin/impersonate",
        json={
            "user_id": str(club_user.id),
            "tenant_id": str(test_tenant.id),
            "reason": "for the audit listing",
        },
    )
    await superuser_client.post("/api/v1/admin/impersonate/stop")

    resp = await superuser_client.get(
        "/api/v1/admin/audit-log", params={"action": "impersonation.start"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["actor_email"] == superuser.email
    assert data[0]["target_id"] == str(club_user.id)
