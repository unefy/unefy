"""Tests for tenant-managed measurement units and club disciplines."""

import json
import uuid
from collections.abc import AsyncGenerator

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models.discipline import Discipline
from app.models.tenant import Tenant
from app.models.user import User


async def _create_unit(
    client: AsyncClient, *, name: str = "Ringe", symbol: str | None = None
) -> dict:
    resp = await client.post("/api/v1/units", json={"name": name, "symbol": symbol})
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _create_discipline(
    client: AsyncClient,
    *,
    name: str = "Luftgewehr",
    short_name: str | None = "LG",
    default_unit: str | None = "Ringe",
) -> dict:
    resp = await client.post(
        "/api/v1/club-disciplines",
        json={"name": name, "short_name": short_name, "default_unit": default_unit},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _add_catalog_discipline(
    session: AsyncSession, *, name: str, scoring_unit: str = "Ringe"
) -> Discipline:
    discipline = Discipline(
        id=uuid.uuid4(),
        slug=f"test-{uuid.uuid4().hex[:8]}",
        name=name,
        short_name="LG 10m",
        federation="DSB",
        category="Luftdruck",
        scoring_unit=scoring_unit,
    )
    session.add(discipline)
    await session.flush()
    return discipline


async def _build_client_for(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str = "owner",
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
        json.dumps({"user_id": str(user_id), "tenant_id": str(tenant_id), "role": role}),
        ex=604800,
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": token},
    )


# --- Measurement units ---


async def test_create_and_list_units(auth_client: AsyncClient) -> None:
    created = await _create_unit(auth_client, name="Sekunden", symbol="s")
    assert created["name"] == "Sekunden"
    assert created["symbol"] == "s"
    assert created["is_active"] is True

    resp = await auth_client.get("/api/v1/units")
    assert resp.status_code == 200
    names = [u["name"] for u in resp.json()["data"]]
    assert "Sekunden" in names


async def test_create_unit_duplicate_name_conflict(auth_client: AsyncClient) -> None:
    await _create_unit(auth_client, name="Ringe")
    resp = await auth_client.post("/api/v1/units", json={"name": "Ringe"})
    assert resp.status_code == 409


async def test_create_unit_empty_name_invalid(auth_client: AsyncClient) -> None:
    resp = await auth_client.post("/api/v1/units", json={"name": ""})
    assert resp.status_code == 422


async def test_update_unit(auth_client: AsyncClient) -> None:
    created = await _create_unit(auth_client, name="Meter")
    resp = await auth_client.patch(
        f"/api/v1/units/{created['id']}",
        json={"name": "Kilometer", "symbol": "km", "is_active": False},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "Kilometer"
    assert data["symbol"] == "km"
    assert data["is_active"] is False

    resp = await auth_client.get("/api/v1/units")
    assert data["id"] not in [u["id"] for u in resp.json()["data"]]
    resp = await auth_client.get("/api/v1/units?include_inactive=true")
    assert data["id"] in [u["id"] for u in resp.json()["data"]]


async def test_update_unit_duplicate_name_conflict(auth_client: AsyncClient) -> None:
    await _create_unit(auth_client, name="Ringe")
    other = await _create_unit(auth_client, name="Punkte")
    resp = await auth_client.patch(f"/api/v1/units/{other['id']}", json={"name": "Ringe"})
    assert resp.status_code == 409


async def test_update_unit_not_found(auth_client: AsyncClient) -> None:
    resp = await auth_client.patch(f"/api/v1/units/{uuid.uuid4()}", json={"name": "X"})
    assert resp.status_code == 404


async def test_delete_unit(auth_client: AsyncClient) -> None:
    created = await _create_unit(auth_client)
    resp = await auth_client.delete(f"/api/v1/units/{created['id']}")
    assert resp.status_code == 204

    resp = await auth_client.get("/api/v1/units?include_inactive=true")
    assert created["id"] not in [u["id"] for u in resp.json()["data"]]


async def test_units_require_auth(anon_client: AsyncClient) -> None:
    resp = await anon_client.get("/api/v1/units")
    assert resp.status_code == 403


async def test_units_member_role_forbidden(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    fake_redis,  # type: ignore[no-untyped-def]
) -> None:
    member_client = await _build_client_for(
        db_session, fake_redis, uuid.uuid4(), test_tenant.id, role="member"
    )
    try:
        resp = await member_client.get("/api/v1/units")
        assert resp.status_code == 403
    finally:
        await member_client.aclose()


# --- Club disciplines ---


async def test_create_and_list_disciplines(auth_client: AsyncClient) -> None:
    created = await _create_discipline(auth_client)
    assert created["name"] == "Luftgewehr"
    assert created["short_name"] == "LG"
    assert created["default_unit"] == "Ringe"

    resp = await auth_client.get("/api/v1/club-disciplines")
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()["data"]]
    assert "Luftgewehr" in names


async def test_create_discipline_duplicate_name_conflict(auth_client: AsyncClient) -> None:
    await _create_discipline(auth_client)
    resp = await auth_client.post("/api/v1/club-disciplines", json={"name": "Luftgewehr"})
    assert resp.status_code == 409


async def test_update_discipline(auth_client: AsyncClient) -> None:
    created = await _create_discipline(auth_client)
    resp = await auth_client.patch(
        f"/api/v1/club-disciplines/{created['id']}",
        json={"name": "Luftpistole", "default_unit": "Punkte"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "Luftpistole"
    assert data["default_unit"] == "Punkte"


async def test_delete_discipline(auth_client: AsyncClient) -> None:
    created = await _create_discipline(auth_client)
    resp = await auth_client.delete(f"/api/v1/club-disciplines/{created['id']}")
    assert resp.status_code == 204

    resp = await auth_client.get("/api/v1/club-disciplines?include_inactive=true")
    assert created["id"] not in [d["id"] for d in resp.json()["data"]]


async def test_disciplines_require_auth(anon_client: AsyncClient) -> None:
    resp = await anon_client.get("/api/v1/club-disciplines")
    assert resp.status_code == 403


# --- Import from catalog ---


async def test_import_disciplines_from_catalog(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    entry = await _add_catalog_discipline(db_session, name="Luftgewehr", scoring_unit="Ringe")

    resp = await auth_client.post(
        "/api/v1/club-disciplines/import", json={"discipline_ids": [str(entry.id)]}
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Luftgewehr"
    assert data[0]["short_name"] == "LG 10m"
    assert data[0]["default_unit"] == "Ringe"


async def test_import_disciplines_skips_existing_names(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _create_discipline(auth_client, name="Luftgewehr")
    entry = await _add_catalog_discipline(db_session, name="Luftgewehr")

    resp = await auth_client.post(
        "/api/v1/club-disciplines/import", json={"discipline_ids": [str(entry.id)]}
    )
    assert resp.status_code == 201
    assert resp.json()["data"] == []

    resp = await auth_client.get("/api/v1/club-disciplines")
    assert len([d for d in resp.json()["data"] if d["name"] == "Luftgewehr"]) == 1


async def test_import_disciplines_empty_list_invalid(auth_client: AsyncClient) -> None:
    resp = await auth_client.post("/api/v1/club-disciplines/import", json={"discipline_ids": []})
    assert resp.status_code == 422


# --- Tenant isolation ---


async def test_catalog_is_tenant_scoped(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
) -> None:
    unit = await _create_unit(auth_client, name="Ringe")
    discipline = await _create_discipline(auth_client)

    other_tenant = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other_tenant)
    await db_session.flush()

    other_client = await _build_client_for(db_session, fake_redis, uuid.uuid4(), other_tenant.id)
    try:
        resp = await other_client.get("/api/v1/units")
        assert resp.json()["data"] == []

        resp = await other_client.get("/api/v1/club-disciplines")
        assert resp.json()["data"] == []

        resp = await other_client.patch(f"/api/v1/units/{unit['id']}", json={"name": "X"})
        assert resp.status_code == 404

        resp = await other_client.delete(f"/api/v1/club-disciplines/{discipline['id']}")
        assert resp.status_code == 404
    finally:
        await other_client.aclose()


async def test_a_member_may_read_the_discipline_catalogue(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_user: User,
    test_tenant: Tenant,
) -> None:
    """A discipline name is configuration, not anybody's data.

    Board-only meant the discipline column of a member's own range days was
    silently empty — the read fell to 403 and the page showed dashes.
    """
    import json as json_module

    from httpx import ASGITransport

    import app.redis as redis_module
    from app.database import get_db_session
    from app.main import app

    async def override_db():  # type: ignore[no-untyped-def]
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    redis_module._redis_client = fake_redis

    token = uuid.uuid4().hex
    await fake_redis.set(
        f"session:{token}",
        json_module.dumps(
            {
                "user_id": str(test_user.id),
                "tenant_id": str(test_tenant.id),
                "role": "member",
            }
        ),
        ex=604800,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": token},
    ) as client:
        assert (await client.get("/api/v1/club-disciplines")).status_code == 200
        # Writing stays board work.
        assert (
            await client.post("/api/v1/club-disciplines", json={"name": "Neu"})
        ).status_code == 403
