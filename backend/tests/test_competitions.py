"""Tests for Competition/Session/Entry API.

Covers CRUD, idempotent entry create, scoreboard, and tenant isolation.
"""

import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import create_access_token
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User


def _bearer(user: User, tenant: Tenant, role: str = "owner") -> dict[str, str]:
    token, _ = create_access_token(user_id=user.id, tenant_id=tenant.id, role=role)
    return {"Authorization": f"Bearer {token}"}


async def _seed_member(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    number: str = "001",
    name: str = "Max",
) -> Member:
    member = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_number=number,
        first_name=name,
        last_name="Test",
        joined_at=date(2024, 1, 1),
        status="active",
    )
    session.add(member)
    await session.flush()
    return member


async def _create_competition(
    client: AsyncClient,
    headers: dict[str, str],
    **kwargs: object,
) -> dict:
    defaults = {
        "name": "Test Competition",
        "start_date": "2026-06-01",
        "scoring_unit": "Ringe",
        "scoring_mode": "highest_wins",
    }
    defaults.update(kwargs)
    resp = await client.post("/api/v1/competitions", json=defaults, headers=headers)
    assert resp.status_code == 200
    return resp.json()["data"]


async def _create_session(
    client: AsyncClient,
    headers: dict[str, str],
    comp_id: str,
    **kwargs: object,
) -> dict:
    defaults = {"date": "2026-06-15"}
    defaults.update(kwargs)
    resp = await client.post(
        f"/api/v1/competitions/{comp_id}/sessions",
        json=defaults,
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()["data"]


# --- Competition CRUD ---


async def test_competition_crud(
    client: AsyncClient,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    h = _bearer(test_user, test_tenant)
    comp = await _create_competition(client, h, name="Liga 2026", competition_type="league")
    assert comp["competition_type"] == "league"
    assert comp["scoring_unit"] == "Ringe"

    # List
    resp = await client.get("/api/v1/competitions", headers=h)
    assert resp.json()["meta"]["total"] >= 1

    # Update
    resp = await client.patch(
        f"/api/v1/competitions/{comp['id']}",
        json={"name": "Liga 2026 Updated"},
        headers=h,
    )
    assert resp.json()["data"]["name"] == "Liga 2026 Updated"

    # Delete
    resp = await client.delete(f"/api/v1/competitions/{comp['id']}", headers=h)
    assert resp.status_code == 200
    resp = await client.get(f"/api/v1/competitions/{comp['id']}", headers=h)
    assert resp.status_code == 404


# --- Session CRUD ---


async def test_session_crud(
    client: AsyncClient,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    h = _bearer(test_user, test_tenant)
    comp = await _create_competition(client, h)
    sess = await _create_session(client, h, comp["id"], name="Runde 1", discipline="LG 10m")
    assert sess["discipline"] == "LG 10m"

    # List
    resp = await client.get(f"/api/v1/competitions/{comp['id']}/sessions", headers=h)
    assert resp.json()["meta"]["total"] == 1

    # Delete
    resp = await client.delete(
        f"/api/v1/competitions/{comp['id']}/sessions/{sess['id']}",
        headers=h,
    )
    assert resp.status_code == 200


# --- Entry CRUD + Idempotency ---


async def test_entry_crud_and_idempotency(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    h = _bearer(test_user, test_tenant)
    member = await _seed_member(db_session, test_tenant.id)
    comp = await _create_competition(client, h)
    sess = await _create_session(client, h, comp["id"])

    base_url = f"/api/v1/competitions/{comp['id']}/sessions/{sess['id']}/entries"

    # Create entry
    entry_payload = {
        "member_id": str(member.id),
        "score_value": 95.0,
        "score_unit": "Ringe",
        "discipline": "LG 10m",
        "details": {
            "shots": [
                {"ring": 10, "x": 0.02, "y": -0.01},
                {"ring": 9, "x": 0.15, "y": 0.08},
            ],
            "target_type": "air_rifle_10m",
        },
        "source": "manual",
        "recorded_at": "2026-06-15T14:30:00+00:00",
    }
    resp = await client.post(base_url, json=entry_payload, headers=h)
    assert resp.status_code == 200
    entry = resp.json()["data"]
    assert float(entry["score_value"]) == 95.0
    assert entry["details"]["target_type"] == "air_rifle_10m"
    assert len(entry["details"]["shots"]) == 2

    # Idempotent: same client UUID
    client_uuid = str(uuid.uuid4())
    entry_payload["id"] = client_uuid
    resp1 = await client.post(base_url, json=entry_payload, headers=h)
    resp2 = await client.post(base_url, json=entry_payload, headers=h)
    assert resp1.json()["data"]["id"] == resp2.json()["data"]["id"]

    # List
    resp = await client.get(base_url, headers=h)
    assert resp.json()["meta"]["total"] == 2  # original + idempotent one

    # Update
    resp = await client.patch(
        f"{base_url}/{entry['id']}",
        json={"score_value": 97.0},
        headers=h,
    )
    assert float(resp.json()["data"]["score_value"]) == 97.0

    # Delete
    resp = await client.delete(f"{base_url}/{entry['id']}", headers=h)
    assert resp.status_code == 200


# --- Scoreboard ---


async def test_scoreboard(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    h = _bearer(test_user, test_tenant)
    m1 = await _seed_member(db_session, test_tenant.id, "S01", "Alice")
    m2 = await _seed_member(db_session, test_tenant.id, "S02", "Bob")

    comp = await _create_competition(client, h, name="Liga", competition_type="league")
    s1 = await _create_session(client, h, comp["id"], name="Runde 1", date="2026-01-15")
    s2 = await _create_session(client, h, comp["id"], name="Runde 2", date="2026-02-15")

    base1 = f"/api/v1/competitions/{comp['id']}/sessions/{s1['id']}/entries"
    base2 = f"/api/v1/competitions/{comp['id']}/sessions/{s2['id']}/entries"

    # Runde 1
    for mid, score in [(m1.id, 95), (m2.id, 90)]:
        await client.post(
            base1,
            json={
                "member_id": str(mid),
                "score_value": score,
                "recorded_at": "2026-01-15T10:00:00+00:00",
            },
            headers=h,
        )

    # Runde 2
    for mid, score in [(m1.id, 97), (m2.id, 93)]:
        await client.post(
            base2,
            json={
                "member_id": str(mid),
                "score_value": score,
                "recorded_at": "2026-02-15T10:00:00+00:00",
            },
            headers=h,
        )

    # Scoreboard
    resp = await client.get(f"/api/v1/competitions/{comp['id']}/scoreboard", headers=h)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    # Alice should be rank 1 (192 > 183)
    assert data[0]["rank"] == 1
    assert float(data[0]["total_score"]) == 192.0
    assert data[0]["entry_count"] == 2


# --- Tenant Isolation ---


async def test_competition_tenant_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_tenant: Tenant,
    test_membership: TenantMembership,
) -> None:
    h_a = _bearer(test_user, test_tenant)
    comp = await _create_competition(client, h_a, name="Tenant A Only")

    # Tenant B
    tenant_b = Tenant(id=uuid.uuid4(), name="Other", slug="other-comp")
    db_session.add(tenant_b)
    user_b = User(id=uuid.uuid4(), email="b@test.com", name="B", email_verified=True)
    db_session.add(user_b)
    await db_session.flush()
    db_session.add(
        TenantMembership(
            id=uuid.uuid4(),
            user_id=user_b.id,
            tenant_id=tenant_b.id,
            role="owner",
            is_active=True,
        )
    )
    await db_session.flush()

    h_b = _bearer(user_b, tenant_b)
    resp = await client.get(f"/api/v1/competitions/{comp['id']}", headers=h_b)
    assert resp.status_code == 404

    resp = await client.get("/api/v1/competitions", headers=h_b)
    ids = [c["id"] for c in resp.json()["data"]]
    assert comp["id"] not in ids


async def test_unauthenticated_rejected(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/competitions")
    assert resp.status_code in (401, 403)
