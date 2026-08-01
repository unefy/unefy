"""Tests for platform-admin master data: sports, catalog units, disciplines."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AdminAuditLog
from app.models.discipline import Discipline
from app.models.sport import Sport
from app.models.user import User
from tests.test_admin import _session_client

CATALOG_ENDPOINTS = [
    ("GET", "/api/v1/admin/catalog/sports"),
    ("GET", "/api/v1/admin/catalog/units"),
    ("GET", "/api/v1/admin/catalog/disciplines"),
    ("GET", "/api/v1/admin/catalog/modules"),
]


@pytest.fixture
async def superuser(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="catalog-admin@example.com",
        name="Catalog Admin",
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
async def sport(db_session: AsyncSession) -> Sport:
    entry = Sport(
        id=uuid.uuid4(),
        key="shooting",
        name="Schießsport",
        sort_order=10,
        is_active=True,
        modules=["shooting"],
    )
    db_session.add(entry)
    await db_session.flush()
    return entry


# --- Guard ---


@pytest.mark.parametrize(("method", "path"), CATALOG_ENDPOINTS)
async def test_catalog_endpoints_reject_ordinary_user(
    auth_client: AsyncClient, method: str, path: str
) -> None:
    resp = await auth_client.request(method, path)
    assert resp.status_code == 403, resp.text


@pytest.mark.parametrize(("method", "path"), CATALOG_ENDPOINTS)
async def test_catalog_endpoints_reject_anonymous(
    client: AsyncClient, method: str, path: str
) -> None:
    resp = await client.request(method, path)
    assert resp.status_code == 403, resp.text


async def test_write_endpoints_reject_ordinary_user(auth_client: AsyncClient, sport: Sport) -> None:
    resp = await auth_client.post(
        "/api/v1/admin/catalog/sports",
        json={"key": "football", "name": "Fußball"},
    )
    assert resp.status_code == 403, resp.text


# --- Sports ---


async def test_create_and_list_sport(superuser_client: AsyncClient) -> None:
    resp = await superuser_client.post(
        "/api/v1/admin/catalog/sports",
        json={
            "key": "athletics",
            "name": "Leichtathletik",
            "icon": "Timer",
            "sort_order": 20,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["key"] == "athletics"

    listed = await superuser_client.get("/api/v1/admin/catalog/sports")
    assert listed.status_code == 200
    assert "athletics" in [s["key"] for s in listed.json()["data"]]


async def test_create_sport_rejects_duplicate_key(
    superuser_client: AsyncClient, sport: Sport
) -> None:
    resp = await superuser_client.post(
        "/api/v1/admin/catalog/sports",
        json={"key": sport.key, "name": "Doppelt"},
    )
    assert resp.status_code == 409, resp.text


async def test_create_sport_rejects_bad_key_format(superuser_client: AsyncClient) -> None:
    resp = await superuser_client.post(
        "/api/v1/admin/catalog/sports",
        json={"key": "Ball Sport!", "name": "Ballsport"},
    )
    assert resp.status_code == 422, resp.text


async def test_sport_rejects_unknown_module(superuser_client: AsyncClient) -> None:
    """A module with no code behind it would silently do nothing."""
    resp = await superuser_client.post(
        "/api/v1/admin/catalog/sports",
        json={"key": "curling", "name": "Curling", "modules": ["quidditch"]},
    )
    assert resp.status_code == 422, resp.text


async def test_sport_accepts_known_module(superuser_client: AsyncClient) -> None:
    resp = await superuser_client.post(
        "/api/v1/admin/catalog/sports",
        json={"key": "biathlon", "name": "Biathlon", "modules": ["shooting"]},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["modules"] == ["shooting"]


async def test_update_sport(superuser_client: AsyncClient, sport: Sport) -> None:
    resp = await superuser_client.patch(
        f"/api/v1/admin/catalog/sports/{sport.id}",
        json={"name": "Sportschießen", "is_active": False},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["name"] == "Sportschießen"
    assert resp.json()["data"]["is_active"] is False


async def test_update_sport_cannot_change_key(superuser_client: AsyncClient, sport: Sport) -> None:
    """`key` is referenced elsewhere, so it is absent from the update schema."""
    resp = await superuser_client.patch(
        f"/api/v1/admin/catalog/sports/{sport.id}",
        json={"key": "renamed"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["key"] == sport.key


async def test_delete_sport_with_disciplines_is_refused(
    superuser_client: AsyncClient, sport: Sport, db_session: AsyncSession
) -> None:
    db_session.add(
        Discipline(
            id=uuid.uuid4(),
            sport_id=sport.id,
            slug="lg-10m",
            name="Luftgewehr",
            federation="DSB",
            category="Luftdruck",
        )
    )
    await db_session.flush()

    resp = await superuser_client.delete(f"/api/v1/admin/catalog/sports/{sport.id}")
    assert resp.status_code == 409, resp.text


async def test_delete_empty_sport(superuser_client: AsyncClient, sport: Sport) -> None:
    resp = await superuser_client.delete(f"/api/v1/admin/catalog/sports/{sport.id}")
    assert resp.status_code == 204, resp.text


async def test_sport_404_for_unknown_id(superuser_client: AsyncClient) -> None:
    resp = await superuser_client.patch(
        f"/api/v1/admin/catalog/sports/{uuid.uuid4()}", json={"name": "Neuer Name"}
    )
    assert resp.status_code == 404, resp.text


# --- Units ---


async def test_unit_crud(superuser_client: AsyncClient, sport: Sport) -> None:
    created = await superuser_client.post(
        "/api/v1/admin/catalog/units",
        json={"sport_id": str(sport.id), "name": "Ringe", "sort_order": 0},
    )
    assert created.status_code == 201, created.text
    unit_id = created.json()["data"]["id"]

    updated = await superuser_client.patch(
        f"/api/v1/admin/catalog/units/{unit_id}", json={"symbol": "R"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["symbol"] == "R"

    listed = await superuser_client.get(
        "/api/v1/admin/catalog/units", params={"sport_id": str(sport.id)}
    )
    assert [u["name"] for u in listed.json()["data"]] == ["Ringe"]

    deleted = await superuser_client.delete(f"/api/v1/admin/catalog/units/{unit_id}")
    assert deleted.status_code == 204, deleted.text


async def test_unit_name_unique_per_sport(superuser_client: AsyncClient, sport: Sport) -> None:
    payload = {"sport_id": str(sport.id), "name": "Ringe"}
    assert (
        await superuser_client.post("/api/v1/admin/catalog/units", json=payload)
    ).status_code == 201
    resp = await superuser_client.post("/api/v1/admin/catalog/units", json=payload)
    assert resp.status_code == 409, resp.text


async def test_unit_name_clash_is_case_insensitive(
    superuser_client: AsyncClient, sport: Sport
) -> None:
    await superuser_client.post(
        "/api/v1/admin/catalog/units", json={"sport_id": str(sport.id), "name": "Ringe"}
    )
    resp = await superuser_client.post(
        "/api/v1/admin/catalog/units", json={"sport_id": str(sport.id), "name": "ringe"}
    )
    assert resp.status_code == 409, resp.text


async def test_unit_rejects_unknown_sport(superuser_client: AsyncClient) -> None:
    resp = await superuser_client.post(
        "/api/v1/admin/catalog/units",
        json={"sport_id": str(uuid.uuid4()), "name": "Ringe"},
    )
    assert resp.status_code == 404, resp.text


# --- Disciplines ---


async def test_discipline_crud_and_filtering(superuser_client: AsyncClient, sport: Sport) -> None:
    created = await superuser_client.post(
        "/api/v1/admin/catalog/disciplines",
        json={
            "sport_id": str(sport.id),
            "slug": "dsb-1-40",
            "name": "Luftgewehr",
            "short_name": "LG 10m",
            "federation": "DSB",
            "category": "Luftdruck",
            "scoring_unit": "Ringe",
            "scoring_mode": "highest_wins",
        },
    )
    assert created.status_code == 201, created.text
    discipline_id = created.json()["data"]["id"]

    filtered = await superuser_client.get(
        "/api/v1/admin/catalog/disciplines", params={"federation": "DSB"}
    )
    assert filtered.json()["meta"]["total"] == 1

    searched = await superuser_client.get(
        "/api/v1/admin/catalog/disciplines", params={"search": "luftgew"}
    )
    assert searched.json()["meta"]["total"] == 1

    updated = await superuser_client.patch(
        f"/api/v1/admin/catalog/disciplines/{discipline_id}",
        json={"short_name": "LG"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["short_name"] == "LG"

    deleted = await superuser_client.delete(f"/api/v1/admin/catalog/disciplines/{discipline_id}")
    assert deleted.status_code == 204, deleted.text


async def test_discipline_rejects_duplicate_slug(
    superuser_client: AsyncClient, sport: Sport
) -> None:
    payload = {
        "sport_id": str(sport.id),
        "slug": "dsb-1-40",
        "name": "Luftgewehr",
        "federation": "DSB",
        "category": "Luftdruck",
    }
    assert (
        await superuser_client.post("/api/v1/admin/catalog/disciplines", json=payload)
    ).status_code == 201
    resp = await superuser_client.post("/api/v1/admin/catalog/disciplines", json=payload)
    assert resp.status_code == 409, resp.text


async def test_discipline_rejects_unknown_scoring_mode(
    superuser_client: AsyncClient, sport: Sport
) -> None:
    """Each scoring mode needs a ranking implementation — it is a closed set."""
    resp = await superuser_client.post(
        "/api/v1/admin/catalog/disciplines",
        json={
            "sport_id": str(sport.id),
            "slug": "weird",
            "name": "Weird",
            "federation": "X",
            "category": "Y",
            "scoring_mode": "vibes",
        },
    )
    assert resp.status_code == 422, resp.text


# --- Audit ---


async def test_catalog_changes_are_audited(
    superuser_client: AsyncClient, superuser: User, db_session: AsyncSession
) -> None:
    await superuser_client.post(
        "/api/v1/admin/catalog/sports", json={"key": "rowing", "name": "Rudern"}
    )

    entries = (
        (
            await db_session.execute(
                select(AdminAuditLog).where(AdminAuditLog.action == "sport.create")
            )
        )
        .scalars()
        .all()
    )
    assert len(entries) == 1
    assert entries[0].actor_user_id == superuser.id
    assert entries[0].payload is not None
    assert entries[0].payload["key"] == "rowing"
