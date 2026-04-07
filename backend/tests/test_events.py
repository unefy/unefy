"""Tests for events + shooting results API.

Covers:
- Events CRUD (create, list, get, update, delete)
- Results CRUD (create, list, get, update, delete)
- Result idempotent create (offline sync)
- Tenant isolation for events and results
"""

import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import create_access_token
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User

# --- Fixtures ------------------------------------------------------------------


async def _seed_member(session: AsyncSession, tenant_id: uuid.UUID, number: str = "001") -> Member:
    member = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_number=number,
        first_name="Max",
        last_name="Mustermann",
        joined_at=date(2024, 1, 1),
        status="active",
    )
    session.add(member)
    await session.flush()
    return member


def _bearer(user: User, tenant: Tenant, role: str = "owner") -> dict[str, str]:
    token, _ = create_access_token(user_id=user.id, tenant_id=tenant.id, role=role)
    return {"Authorization": f"Bearer {token}"}


# --- Events CRUD ---------------------------------------------------------------


async def test_create_event(
    client: AsyncClient,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    headers = _bearer(test_user, test_tenant)
    response = await client.post(
        "/api/v1/events",
        json={
            "name": "Club-Meisterschaft 2026",
            "date": "2026-06-15",
            "location": "Schießstand Halle 3",
            "event_type": "competition",
            "discipline": "air_rifle_10m",
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Club-Meisterschaft 2026"
    assert data["date"] == "2026-06-15"
    assert data["discipline"] == "air_rifle_10m"
    assert "id" in data


async def test_list_events(
    client: AsyncClient,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    headers = _bearer(test_user, test_tenant)
    # Create two events.
    for name in ["Event A", "Event B"]:
        await client.post(
            "/api/v1/events",
            json={"name": name, "date": "2026-07-01"},
            headers=headers,
        )

    response = await client.get("/api/v1/events", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] >= 2
    assert len(body["data"]) >= 2


async def test_get_update_delete_event(
    client: AsyncClient,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    headers = _bearer(test_user, test_tenant)
    create = await client.post(
        "/api/v1/events",
        json={"name": "Trainingslager", "date": "2026-08-01"},
        headers=headers,
    )
    event_id = create.json()["data"]["id"]

    # Get
    get_resp = await client.get(f"/api/v1/events/{event_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["name"] == "Trainingslager"

    # Update
    patch = await client.patch(
        f"/api/v1/events/{event_id}",
        json={"name": "Sommer-Trainingslager"},
        headers=headers,
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["name"] == "Sommer-Trainingslager"

    # Delete
    delete = await client.delete(f"/api/v1/events/{event_id}", headers=headers)
    assert delete.status_code == 200

    # After delete, GET returns 404 (soft-deleted).
    get_after = await client.get(f"/api/v1/events/{event_id}", headers=headers)
    assert get_after.status_code == 404


# --- Results CRUD ---------------------------------------------------------------


async def test_create_and_list_results(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    headers = _bearer(test_user, test_tenant)
    member = await _seed_member(db_session, test_tenant.id)

    # Create event.
    event_resp = await client.post(
        "/api/v1/events",
        json={"name": "Wettkampf", "date": "2026-09-01", "discipline": "air_rifle_10m"},
        headers=headers,
    )
    event_id = event_resp.json()["data"]["id"]

    # Create result.
    result_resp = await client.post(
        f"/api/v1/events/{event_id}/results",
        json={
            "member_id": str(member.id),
            "discipline": "air_rifle_10m",
            "shots": [10, 9, 10, 8, 10, 9, 10, 10, 9, 10],
            "source": "manual",
            "recorded_at": "2026-09-01T14:30:00+00:00",
        },
        headers=headers,
    )
    assert result_resp.status_code == 200
    result = result_resp.json()["data"]
    assert result["total_score"] == 95
    assert result["shot_count"] == 10
    assert result["shots"] == [10, 9, 10, 8, 10, 9, 10, 10, 9, 10]
    assert result["member_id"] == str(member.id)

    # List results.
    list_resp = await client.get(f"/api/v1/events/{event_id}/results", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["meta"]["total"] == 1


async def test_result_idempotent_create(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    """Posting the same client-UUID twice returns the original result, not a duplicate."""
    headers = _bearer(test_user, test_tenant)
    member = await _seed_member(db_session, test_tenant.id, number="002")

    event_resp = await client.post(
        "/api/v1/events",
        json={"name": "Idempotenz-Test", "date": "2026-10-01"},
        headers=headers,
    )
    event_id = event_resp.json()["data"]["id"]

    client_uuid = str(uuid.uuid4())
    payload = {
        "id": client_uuid,
        "member_id": str(member.id),
        "discipline": "air_pistol_10m",
        "shots": [9, 9, 10],
        "source": "scan",
        "recorded_at": "2026-10-01T10:00:00+00:00",
    }

    resp1 = await client.post(f"/api/v1/events/{event_id}/results", json=payload, headers=headers)
    resp2 = await client.post(f"/api/v1/events/{event_id}/results", json=payload, headers=headers)

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["data"]["id"] == resp2.json()["data"]["id"]

    # Only one result exists.
    list_resp = await client.get(f"/api/v1/events/{event_id}/results", headers=headers)
    assert list_resp.json()["meta"]["total"] == 1


async def test_result_validation_ring_out_of_range(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    headers = _bearer(test_user, test_tenant)
    member = await _seed_member(db_session, test_tenant.id, number="003")

    event_resp = await client.post(
        "/api/v1/events",
        json={"name": "Validation-Test", "date": "2026-11-01"},
        headers=headers,
    )
    event_id = event_resp.json()["data"]["id"]

    resp = await client.post(
        f"/api/v1/events/{event_id}/results",
        json={
            "member_id": str(member.id),
            "discipline": "air_rifle_10m",
            "shots": [10, 11],  # 11 is out of range!
            "recorded_at": "2026-11-01T10:00:00+00:00",
        },
        headers=headers,
    )
    assert resp.status_code == 422


# --- Tenant isolation -----------------------------------------------------------


async def test_events_tenant_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    """User from tenant A cannot see events of tenant B."""
    headers_a = _bearer(test_user, test_tenant)

    # Create event in tenant A.
    resp_a = await client.post(
        "/api/v1/events",
        json={"name": "Tenant-A-Event", "date": "2026-12-01"},
        headers=headers_a,
    )
    event_id_a = resp_a.json()["data"]["id"]

    # Create tenant B + user B.
    tenant_b = Tenant(id=uuid.uuid4(), name="Other Club", slug="other")
    db_session.add(tenant_b)
    user_b = User(
        id=uuid.uuid4(),
        email="other@example.com",
        name="Other User",
        email_verified=True,
    )
    db_session.add(user_b)
    await db_session.flush()
    membership_b = TenantMembership(
        id=uuid.uuid4(),
        user_id=user_b.id,
        tenant_id=tenant_b.id,
        role="owner",
        is_active=True,
    )
    db_session.add(membership_b)
    await db_session.flush()

    headers_b = _bearer(user_b, tenant_b)

    # Tenant B listing should NOT include tenant A's event.
    list_b = await client.get("/api/v1/events", headers=headers_b)
    assert list_b.status_code == 200
    ids_b = [e["id"] for e in list_b.json()["data"]]
    assert event_id_a not in ids_b

    # Tenant B direct access should return 404.
    get_b = await client.get(f"/api/v1/events/{event_id_a}", headers=headers_b)
    assert get_b.status_code == 404


async def test_unauthenticated_access_rejected(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/events")
    assert resp.status_code in (401, 403)
