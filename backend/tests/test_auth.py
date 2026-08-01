import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models.catalog import MeasurementUnit
from app.models.division import Division
from app.models.sport import CatalogUnit, Sport
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User

# Units the seeded sport offers, copied into every club created for it.
SHOOTING_UNITS = [("Ringe", None), ("Punkte", "Pkt.")]


@pytest.fixture
async def shooting_sport(db_session: AsyncSession) -> Sport:
    sport = Sport(
        id=uuid.uuid4(), key="shooting", name="Schie\u00dfsport", is_active=True, modules=[]
    )
    db_session.add(sport)
    await db_session.flush()
    for order, (name, symbol) in enumerate(SHOOTING_UNITS):
        db_session.add(
            CatalogUnit(
                id=uuid.uuid4(), sport_id=sport.id, name=name, symbol=symbol, sort_order=order
            )
        )
    await db_session.flush()
    return sport


def club_payload(name: str = "My New Club", **overrides: object) -> dict:
    payload: dict = {
        "club_name": name,
        "has_divisions": False,
        "divisions": [{"name": name, "sport_key": "shooting"}],
    }
    payload.update(overrides)
    return payload


# --- GET /api/v1/auth/me ---


async def test_me_with_valid_session(
    auth_client: AsyncClient,
    test_user: User,
    test_tenant: Tenant,
) -> None:
    """Authenticated user gets their profile with tenant context."""
    response = await auth_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data is not None
    assert data["user"]["id"] == str(test_user.id)
    assert data["user"]["name"] == test_user.name
    assert data["user"]["email"] == test_user.email
    assert data["tenant_id"] == str(test_tenant.id)
    assert data["tenant_name"] == test_tenant.name
    assert data["role"] == "owner"
    assert data["needs_onboarding"] is False


async def test_me_without_session(anon_client: AsyncClient) -> None:
    """Unauthenticated request returns data: null."""
    response = await anon_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json() == {"data": None}


async def test_me_with_invalid_session(anon_client: AsyncClient) -> None:
    """Request with a bogus session cookie returns data: null."""
    response = await anon_client.get(
        "/api/v1/auth/me",
        cookies={"unefy_session": "invalid-token-that-does-not-exist"},
    )
    assert response.status_code == 200
    assert response.json() == {"data": None}


async def test_me_onboarding_user(
    onboarding_client: AsyncClient,
    test_user: User,
) -> None:
    """User in onboarding state (no tenant) sees needs_onboarding=True."""
    response = await onboarding_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data is not None
    assert data["user"]["id"] == str(test_user.id)
    assert data["tenant_id"] is None
    assert data["needs_onboarding"] is True


# --- POST /api/v1/auth/onboarding/create-club ---


async def test_create_club_success(
    onboarding_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    shooting_sport: Sport,
) -> None:
    """Authenticated user without a tenant can create a club."""
    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club",
        json=club_payload(),
    )
    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data["name"] == "My New Club"
    assert "tenant_id" in data
    # Slug is derived from the club name, not random.
    assert data["slug"] == "my-new-club"

    # Verify tenant was created in DB
    tenant_id = uuid.UUID(data["tenant_id"])
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    result = await db_session.execute(stmt)
    tenant = result.scalar_one_or_none()
    assert tenant is not None
    assert tenant.name == "My New Club"

    # Verify membership was created
    stmt = select(TenantMembership).where(
        TenantMembership.user_id == test_user.id,
        TenantMembership.tenant_id == tenant_id,
    )
    result = await db_session.execute(stmt)
    membership = result.scalar_one_or_none()
    assert membership is not None
    assert membership.role == "owner"

    # Units come from the chosen sport's catalog, not a flat global list.
    stmt = select(MeasurementUnit).where(MeasurementUnit.tenant_id == tenant_id)
    result = await db_session.execute(stmt)
    unit_names = {u.name for u in result.scalars().all()}
    assert unit_names == {name for name, _ in SHOOTING_UNITS}

    # A club always has exactly one primary division, even without Sparten.
    stmt = select(Division).where(Division.tenant_id == tenant_id)
    result = await db_session.execute(stmt)
    divisions = list(result.scalars().all())
    assert len(divisions) == 1
    assert divisions[0].is_primary is True
    assert divisions[0].sport_id == shooting_sport.id
    assert tenant.has_divisions is False


async def test_create_club_fails_without_auth(anon_client: AsyncClient) -> None:
    """Unauthenticated request to create-club returns 403."""
    response = await anon_client.post(
        "/api/v1/auth/onboarding/create-club",
        json=club_payload("Unauthorized Club"),
    )
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "FORBIDDEN"


async def test_create_club_fails_with_empty_name(
    onboarding_client: AsyncClient,
) -> None:
    """Empty club_name fails validation (min_length=2)."""
    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club",
        json=club_payload("", divisions=[{"name": "X", "sport_key": "shooting"}]),
    )
    assert response.status_code == 422


async def test_create_club_fails_with_short_name(
    onboarding_client: AsyncClient,
) -> None:
    """Single-char club_name fails validation (min_length=2)."""
    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club",
        json=club_payload("A", divisions=[{"name": "X", "sport_key": "shooting"}]),
    )
    assert response.status_code == 422


async def test_user_can_create_a_second_club(
    auth_client: AsyncClient,
    test_membership: TenantMembership,
    shooting_sport: Sport,
) -> None:
    """Multi-club is supported — owning one club no longer blocks the next."""
    response = await auth_client.post(
        "/api/v1/auth/onboarding/create-club",
        json=club_payload("Second Club"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["name"] == "Second Club"


async def test_create_club_rejects_unknown_sport(
    onboarding_client: AsyncClient,
) -> None:
    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club",
        json=club_payload(divisions=[{"name": "Quidditch", "sport_key": "quidditch"}]),
    )
    assert response.status_code == 422, response.text


async def test_create_club_without_divisions_rejects_multiple_sports(
    onboarding_client: AsyncClient,
    shooting_sport: Sport,
) -> None:
    """`has_divisions=False` means one sport — two would have no home."""
    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club",
        json=club_payload(
            has_divisions=False,
            divisions=[
                {"name": "Gewehr", "sport_key": "shooting"},
                {"name": "Bogen", "sport_key": "shooting"},
            ],
        ),
    )
    assert response.status_code == 422, response.text


async def test_create_club_with_divisions(
    onboarding_client: AsyncClient,
    db_session: AsyncSession,
    shooting_sport: Sport,
) -> None:
    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club",
        json=club_payload(
            has_divisions=True,
            divisions=[
                {"name": "Gewehr", "sport_key": "shooting"},
                {"name": "Bogen", "sport_key": "shooting"},
            ],
        ),
    )
    assert response.status_code == 200, response.text

    tenant_id = uuid.UUID(response.json()["data"]["tenant_id"])
    result = await db_session.execute(select(Division).where(Division.tenant_id == tenant_id))
    divisions = sorted(result.scalars().all(), key=lambda d: d.name)
    assert [d.name for d in divisions] == ["Bogen", "Gewehr"]
    # Exactly one primary, regardless of how many divisions there are.
    assert sum(1 for d in divisions if d.is_primary) == 1


async def test_slug_collision_gets_suffix(
    onboarding_client: AsyncClient,
    db_session: AsyncSession,
    shooting_sport: Sport,
) -> None:
    db_session.add(Tenant(name="Taken", slug="my-new-club"))
    await db_session.flush()

    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club", json=club_payload()
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["slug"] == "my-new-club-2"


# --- POST /api/v1/auth/logout ---


async def test_logout_clears_session(
    fake_redis,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    """Logout deletes the Redis session and clears the cookie."""
    from collections.abc import AsyncGenerator

    from httpx import ASGITransport

    import app.redis as redis_module
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession]:  # type: ignore[type-arg]
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    original_redis = redis_module._redis_client
    redis_module._redis_client = fake_redis

    # Create a session
    session_token = uuid.uuid4().hex
    session_data = json.dumps(
        {
            "user_id": str(test_user.id),
            "tenant_id": str(test_tenant.id),
            "role": "owner",
        }
    )
    await fake_redis.set(f"session:{session_token}", session_data, ex=604800)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": session_token},
    ) as ac:
        response = await ac.post("/api/v1/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"data": {"message": "Logged out"}}

    # Session should be deleted from Redis
    raw = await fake_redis.get(f"session:{session_token}")
    assert raw is None

    redis_module._redis_client = original_redis
    app.dependency_overrides.clear()


async def test_logout_without_session(anon_client: AsyncClient) -> None:
    """Logout without a session still returns 200."""
    response = await anon_client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"data": {"message": "Logged out"}}


# --- GET /api/v1/auth/tenants ---


async def test_list_tenants_single_membership(
    auth_client: AsyncClient,
    test_tenant: Tenant,
) -> None:
    """User with one membership gets a single entry marked as current."""
    response = await auth_client.get("/api/v1/auth/tenants")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["tenant_id"] == str(test_tenant.id)
    assert data[0]["role"] == "owner"
    assert data[0]["is_current"] is True


async def test_list_tenants_multiple_memberships(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
) -> None:
    """All active memberships are listed; only the session tenant is current."""
    other_tenant = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other_tenant)
    await db_session.flush()
    db_session.add(
        TenantMembership(
            user_id=test_user.id,
            tenant_id=other_tenant.id,
            role="member",
            is_active=True,
        )
    )
    await db_session.flush()

    response = await auth_client.get("/api/v1/auth/tenants")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    by_id = {entry["tenant_id"]: entry for entry in data}
    assert by_id[str(test_tenant.id)]["is_current"] is True
    assert by_id[str(other_tenant.id)]["is_current"] is False
    assert by_id[str(other_tenant.id)]["role"] == "member"


async def test_list_tenants_excludes_inactive_membership(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
) -> None:
    """Inactive memberships are not listed."""
    other_tenant = Tenant(id=uuid.uuid4(), name="Left Club", slug="left-club")
    db_session.add(other_tenant)
    await db_session.flush()
    db_session.add(
        TenantMembership(
            user_id=test_user.id,
            tenant_id=other_tenant.id,
            role="member",
            is_active=False,
        )
    )
    await db_session.flush()

    response = await auth_client.get("/api/v1/auth/tenants")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["tenant_id"] == str(test_tenant.id)


async def test_list_tenants_without_auth(anon_client: AsyncClient) -> None:
    """Unauthenticated request is rejected."""
    response = await anon_client.get("/api/v1/auth/tenants")
    assert response.status_code == 403


# --- POST /api/v1/auth/switch-tenant ---


async def test_switch_tenant_success(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_user: User,
    test_tenant: Tenant,
) -> None:
    """Switching rotates the session cookie and scopes it to the new tenant."""
    other_tenant = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other_tenant)
    await db_session.flush()
    db_session.add(
        TenantMembership(
            user_id=test_user.id,
            tenant_id=other_tenant.id,
            role="board",
            is_active=True,
        )
    )
    await db_session.flush()

    old_token = auth_client.cookies.get("unefy_session")

    response = await auth_client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": str(other_tenant.id)},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["tenant_id"] == str(other_tenant.id)
    assert data["role"] == "board"

    # Old session invalidated
    assert await fake_redis.get(f"session:{old_token}") is None

    # New session cookie set and scoped to the new tenant
    new_token = response.cookies.get("unefy_session")
    assert new_token is not None
    assert new_token != old_token
    raw = await fake_redis.get(f"session:{new_token}")
    session_data = json.loads(raw)
    assert session_data["tenant_id"] == str(other_tenant.id)
    assert session_data["role"] == "board"
    assert session_data["user_id"] == str(test_user.id)


async def test_switch_tenant_without_membership(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Switching to a tenant the user is not a member of is rejected."""
    foreign_tenant = Tenant(id=uuid.uuid4(), name="Foreign Club", slug="foreign-club")
    db_session.add(foreign_tenant)
    await db_session.flush()

    response = await auth_client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": str(foreign_tenant.id)},
    )
    assert response.status_code == 403


async def test_switch_tenant_inactive_membership(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Switching to a tenant with an inactive membership is rejected."""
    other_tenant = Tenant(id=uuid.uuid4(), name="Left Club", slug="left-club")
    db_session.add(other_tenant)
    await db_session.flush()
    db_session.add(
        TenantMembership(
            user_id=test_user.id,
            tenant_id=other_tenant.id,
            role="member",
            is_active=False,
        )
    )
    await db_session.flush()

    response = await auth_client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": str(other_tenant.id)},
    )
    assert response.status_code == 403


async def test_switch_tenant_without_auth(anon_client: AsyncClient) -> None:
    """Unauthenticated request is rejected."""
    response = await anon_client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": str(uuid.uuid4())},
    )
    assert response.status_code == 403
