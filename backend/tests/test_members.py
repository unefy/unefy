"""Tenant isolation tests for the members API.

Members hold GDPR-regulated personal data, so every endpoint MUST be
tenant-scoped. A user belonging to tenant A must never be able to read,
update, or delete members of tenant B, no matter what IDs they send.
"""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import date

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User


async def _add_member(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    member_number: str,
    first_name: str = "Alice",
    last_name: str = "Example",
    status: str = "active",
) -> Member:
    member = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_number=member_number,
        first_name=first_name,
        last_name=last_name,
        joined_at=date(2024, 1, 1),
        status=status,
    )
    session.add(member)
    await session.flush()
    return member


async def _build_client_for(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> AsyncClient:
    import app.redis as redis_module
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession]:  # type: ignore[type-arg]
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    redis_module._redis_client = fake_redis

    token = uuid.uuid4().hex
    await fake_redis.set(
        f"session:{token}",
        json.dumps(
            {
                "user_id": str(user_id),
                "tenant_id": str(tenant_id),
                "role": "owner",
            }
        ),
        ex=604800,
    )

    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": token},
    )


async def test_list_members_is_tenant_scoped(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """GET /members only returns the caller's tenant's members."""
    # Seed: own tenant has 2 members, foreign tenant has 1.
    await _add_member(db_session, test_tenant.id, member_number="001")
    await _add_member(db_session, test_tenant.id, member_number="002")

    foreign_tenant = Tenant(id=uuid.uuid4(), name="Other", slug="other")
    db_session.add(foreign_tenant)
    await db_session.flush()
    foreign_member = await _add_member(
        db_session,
        foreign_tenant.id,
        member_number="999",
        first_name="Foreign",
    )

    client = await _build_client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get("/api/v1/members")

    assert response.status_code == 200
    body = response.json()
    returned_ids = {m["id"] for m in body["data"]}
    assert str(foreign_member.id) not in returned_ids
    assert body["meta"]["total"] == 2


async def test_get_member_cross_tenant_returns_404(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """GET /members/{id} returns 404 when the member belongs to another tenant."""
    foreign_tenant = Tenant(id=uuid.uuid4(), name="Other", slug="other")
    db_session.add(foreign_tenant)
    await db_session.flush()
    foreign_member = await _add_member(db_session, foreign_tenant.id, member_number="999")

    client = await _build_client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get(f"/api/v1/members/{foreign_member.id}")

    assert response.status_code == 404


async def test_update_member_cross_tenant_returns_404(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """PATCH on a foreign member returns 404 and does NOT mutate it."""
    foreign_tenant = Tenant(id=uuid.uuid4(), name="Other", slug="other")
    db_session.add(foreign_tenant)
    await db_session.flush()
    foreign_member = await _add_member(
        db_session,
        foreign_tenant.id,
        member_number="999",
        first_name="Untouched",
    )

    client = await _build_client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.patch(
            f"/api/v1/members/{foreign_member.id}",
            json={"first_name": "Hacked"},
        )

    assert response.status_code == 404
    # Confirm nothing changed
    await db_session.refresh(foreign_member)
    assert foreign_member.first_name == "Untouched"


async def test_delete_member_cross_tenant_returns_404(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """DELETE on a foreign member returns 404 and does not soft-delete."""
    foreign_tenant = Tenant(id=uuid.uuid4(), name="Other", slug="other")
    db_session.add(foreign_tenant)
    await db_session.flush()
    foreign_member = await _add_member(db_session, foreign_tenant.id, member_number="999")

    client = await _build_client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.delete(f"/api/v1/members/{foreign_member.id}")

    assert response.status_code == 404
    await db_session.refresh(foreign_member)
    assert foreign_member.deleted_at is None


async def test_bulk_delete_only_affects_own_tenant(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """Bulk delete silently skips foreign member IDs — own tenant only."""
    own_member = await _add_member(db_session, test_tenant.id, member_number="001")
    foreign_tenant = Tenant(id=uuid.uuid4(), name="Other", slug="other")
    db_session.add(foreign_tenant)
    await db_session.flush()
    foreign_member = await _add_member(db_session, foreign_tenant.id, member_number="999")

    client = await _build_client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.post(
            "/api/v1/members/bulk-delete",
            json={"ids": [str(own_member.id), str(foreign_member.id)]},
        )

    assert response.status_code == 200
    assert response.json()["data"]["deleted"] == 1

    await db_session.refresh(own_member)
    await db_session.refresh(foreign_member)
    assert own_member.deleted_at is not None
    assert foreign_member.deleted_at is None


async def test_status_counts_ignore_other_tenants(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """meta.status_counts only counts the caller's tenant's members."""
    await _add_member(db_session, test_tenant.id, member_number="001", status="active")
    await _add_member(db_session, test_tenant.id, member_number="002", status="active")
    foreign_tenant = Tenant(id=uuid.uuid4(), name="Other", slug="other")
    db_session.add(foreign_tenant)
    await db_session.flush()
    for i in range(5):
        await _add_member(
            db_session,
            foreign_tenant.id,
            member_number=f"9{i:02d}",
            status="active",
        )

    client = await _build_client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get("/api/v1/members")

    assert response.status_code == 200
    counts = response.json()["meta"]["status_counts"]
    assert counts.get("active", 0) == 2


async def test_sort_by_invalid_value_rejected(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """sort_by accepts only allowlisted columns (422 otherwise)."""
    client = await _build_client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get("/api/v1/members?sort_by=__class__")

    assert response.status_code == 422
