"""Club functions (Ämter): CRUD, terms of office, holders, onboarding seeding."""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import date
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models.division import Division
from app.models.function import CatalogFunction, Function, MemberFunction
from app.models.member import Member
from app.models.sport import Sport
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User


async def _build_client_for(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
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


def _member(tenant_id: uuid.UUID, **overrides: object) -> Member:
    fields: dict[str, object] = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "member_number": uuid.uuid4().hex[:8],
        "first_name": "Alice",
        "last_name": "Example",
        "joined_at": date(2020, 1, 1),
        "status": "active",
    }
    fields.update(overrides)
    return Member(**fields)


def _function(tenant_id: uuid.UUID, **overrides: object) -> Function:
    fields: dict[str, object] = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "name": "Kassier",
        "level": "club",
        "sort_order": 10,
        "is_active": True,
    }
    fields.update(overrides)
    return Function(**fields)


@pytest.fixture
async def member(db_session: AsyncSession, test_tenant: Tenant) -> Member:
    m = _member(test_tenant.id)
    db_session.add(m)
    await db_session.flush()
    return m


@pytest.fixture
async def treasurer(db_session: AsyncSession, test_tenant: Tenant) -> Function:
    f = _function(test_tenant.id, name="Kassier")
    db_session.add(f)
    await db_session.flush()
    return f


# --- Functions CRUD ---


async def test_function_crud_happy_path(auth_client: AsyncClient) -> None:
    created = await auth_client.post(
        "/api/v1/functions",
        json={"name": "Schriftführer:in", "level": "club", "suggested_role": "board"},
    )
    assert created.status_code == 201
    function = created.json()["data"]
    assert function["name"] == "Schriftführer:in"
    assert function["suggested_role"] == "board"

    listed = await auth_client.get("/api/v1/functions")
    assert listed.status_code == 200
    assert [f["name"] for f in listed.json()["data"]] == ["Schriftführer:in"]

    patched = await auth_client.patch(
        f"/api/v1/functions/{function['id']}", json={"name": "Protokollführer:in"}
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["name"] == "Protokollführer:in"

    deleted = await auth_client.delete(f"/api/v1/functions/{function['id']}")
    assert deleted.status_code == 204

    assert (await auth_client.get("/api/v1/functions")).json()["data"] == []


async def test_create_function_duplicate_name_conflicts(auth_client: AsyncClient) -> None:
    assert (
        await auth_client.post("/api/v1/functions", json={"name": "Kassier"})
    ).status_code == 201
    duplicate = await auth_client.post("/api/v1/functions", json={"name": "Kassier"})
    assert duplicate.status_code == 409


async def test_inactive_functions_hidden_unless_requested(auth_client: AsyncClient) -> None:
    created = await auth_client.post(
        "/api/v1/functions", json={"name": "Waffenwart", "is_active": False}
    )
    assert created.status_code == 201

    assert (await auth_client.get("/api/v1/functions")).json()["data"] == []
    with_inactive = await auth_client.get("/api/v1/functions?include_inactive=true")
    assert [f["name"] for f in with_inactive.json()["data"]] == ["Waffenwart"]


async def test_delete_function_with_history_conflicts(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    member: Member,
    treasurer: Function,
) -> None:
    """Even an ended (historic) term blocks deletion — deactivate instead."""
    db_session.add(
        MemberFunction(
            tenant_id=test_tenant.id,
            member_id=member.id,
            function_id=treasurer.id,
            valid_from=date(2020, 1, 1),
            valid_to=date(2020, 12, 31),
        )
    )
    await db_session.flush()

    response = await auth_client.delete(f"/api/v1/functions/{treasurer.id}")
    assert response.status_code == 409


# --- Terms of office (member functions) ---


async def _assign(
    client: AsyncClient, member_id: uuid.UUID, function_id: uuid.UUID, **overrides: Any
) -> Any:
    payload: dict[str, Any] = {"function_id": str(function_id), "valid_from": "2025-01-01"}
    payload.update(overrides)
    return await client.post(f"/api/v1/members/{member_id}/functions", json=payload)


async def test_assign_and_list_member_functions(
    auth_client: AsyncClient, member: Member, treasurer: Function
) -> None:
    created = await _assign(auth_client, member.id, treasurer.id, note="kommissarisch")
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["function_name"] == "Kassier"
    assert data["valid_to"] is None
    assert data["note"] == "kommissarisch"

    listed = await auth_client.get(f"/api/v1/members/{member.id}/functions")
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


async def test_overlapping_term_conflicts(
    auth_client: AsyncClient, member: Member, treasurer: Function
) -> None:
    assert (await _assign(auth_client, member.id, treasurer.id)).status_code == 201
    overlap = await _assign(auth_client, member.id, treasurer.id, valid_from="2026-06-01")
    assert overlap.status_code == 409


async def test_disjoint_repetition_is_allowed(
    auth_client: AsyncClient, member: Member, treasurer: Function
) -> None:
    """2025 Kassier, 2026 not, from 2027 again — the plan's core scenario."""
    first = await _assign(
        auth_client, member.id, treasurer.id, valid_from="2025-01-01", valid_to="2025-12-31"
    )
    assert first.status_code == 201
    second = await _assign(auth_client, member.id, treasurer.id, valid_from="2027-01-01")
    assert second.status_code == 201


async def test_two_members_in_same_function_are_allowed(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    member: Member,
    treasurer: Function,
) -> None:
    second_member = _member(test_tenant.id, first_name="Bob", last_name="Beispiel")
    db_session.add(second_member)
    await db_session.flush()

    assert (await _assign(auth_client, member.id, treasurer.id)).status_code == 201
    assert (await _assign(auth_client, second_member.id, treasurer.id)).status_code == 201


async def test_club_function_rejects_division(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    member: Member,
    treasurer: Function,
) -> None:
    division = Division(tenant_id=test_tenant.id, name="Pistole", is_primary=True)
    db_session.add(division)
    await db_session.flush()

    response = await _assign(auth_client, member.id, treasurer.id, division_id=str(division.id))
    assert response.status_code == 422


async def test_division_function_requires_division(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    member: Member,
) -> None:
    leader = _function(test_tenant.id, name="Abteilungsleiter:in", level="division")
    division = Division(tenant_id=test_tenant.id, name="Bogen", is_primary=True)
    db_session.add_all([leader, division])
    await db_session.flush()

    missing = await _assign(auth_client, member.id, leader.id)
    assert missing.status_code == 422

    with_division = await _assign(auth_client, member.id, leader.id, division_id=str(division.id))
    assert with_division.status_code == 201
    assert with_division.json()["data"]["division_name"] == "Bogen"


async def test_same_division_function_in_two_divisions(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    member: Member,
) -> None:
    """The same function can be held per division — no false overlap."""
    leader = _function(test_tenant.id, name="Abteilungsleiter:in", level="division")
    pistol = Division(tenant_id=test_tenant.id, name="Pistole", is_primary=True)
    bow = Division(tenant_id=test_tenant.id, name="Bogen", is_primary=False)
    db_session.add_all([leader, pistol, bow])
    await db_session.flush()

    first = await _assign(auth_client, member.id, leader.id, division_id=str(pistol.id))
    assert first.status_code == 201
    second = await _assign(auth_client, member.id, leader.id, division_id=str(bow.id))
    assert second.status_code == 201


async def test_invalid_range_rejected(
    auth_client: AsyncClient, member: Member, treasurer: Function
) -> None:
    response = await _assign(
        auth_client, member.id, treasurer.id, valid_from="2025-06-01", valid_to="2025-01-01"
    )
    assert response.status_code == 422


async def test_end_term_via_patch(
    auth_client: AsyncClient, member: Member, treasurer: Function
) -> None:
    created = await _assign(auth_client, member.id, treasurer.id)
    assignment_id = created.json()["data"]["id"]

    ended = await auth_client.patch(
        f"/api/v1/members/{member.id}/functions/{assignment_id}",
        json={"valid_to": "2026-03-31"},
    )
    assert ended.status_code == 200
    assert ended.json()["data"]["valid_to"] == "2026-03-31"

    # The slot is free again afterwards.
    again = await _assign(auth_client, member.id, treasurer.id, valid_from="2026-04-01")
    assert again.status_code == 201


async def test_delete_assignment(
    auth_client: AsyncClient, member: Member, treasurer: Function
) -> None:
    created = await _assign(auth_client, member.id, treasurer.id)
    assignment_id = created.json()["data"]["id"]

    deleted = await auth_client.delete(f"/api/v1/members/{member.id}/functions/{assignment_id}")
    assert deleted.status_code == 204
    assert (await auth_client.get(f"/api/v1/members/{member.id}/functions")).json()["data"] == []


async def test_assign_to_unknown_member_404(auth_client: AsyncClient, treasurer: Function) -> None:
    response = await _assign(auth_client, uuid.uuid4(), treasurer.id)
    assert response.status_code == 404


async def test_assign_inactive_function_rejected(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    member: Member,
) -> None:
    inactive = _function(test_tenant.id, name="Altamt", is_active=False)
    db_session.add(inactive)
    await db_session.flush()

    response = await _assign(auth_client, member.id, inactive.id)
    assert response.status_code == 422


# --- Holders (Vorstandsliste) ---


async def test_holders_current_and_at_date(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    member: Member,
    treasurer: Function,
) -> None:
    other = _member(test_tenant.id, first_name="Carla", last_name="Vorherig")
    db_session.add(other)
    await db_session.flush()

    # Carla was treasurer in 2025, Alice has held the office since 2026.
    db_session.add_all(
        [
            MemberFunction(
                tenant_id=test_tenant.id,
                member_id=other.id,
                function_id=treasurer.id,
                valid_from=date(2025, 1, 1),
                valid_to=date(2025, 12, 31),
            ),
            MemberFunction(
                tenant_id=test_tenant.id,
                member_id=member.id,
                function_id=treasurer.id,
                valid_from=date(2026, 1, 1),
            ),
        ]
    )
    await db_session.flush()

    current = await auth_client.get("/api/v1/functions/holders")
    assert current.status_code == 200
    holders = current.json()["data"]
    assert len(holders) == 1
    assert holders[0]["member_first_name"] == "Alice"
    assert holders[0]["function_name"] == "Kassier"

    past = await auth_client.get("/api/v1/functions/holders?at=2025-06-01")
    past_holders = past.json()["data"]
    assert len(past_holders) == 1
    assert past_holders[0]["member_first_name"] == "Carla"


# --- Permissions (403 matrix) ---


async def test_member_can_read_holders_but_not_manage(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
    member: Member,
    treasurer: Function,
) -> None:
    client = await _build_client_for(
        db_session, fake_redis, test_user.id, test_tenant.id, role="member"
    )
    async with client as ac:
        assert (await ac.get("/api/v1/functions/holders")).status_code == 200
        assert (await ac.get("/api/v1/functions")).status_code == 403
        assert (await ac.post("/api/v1/functions", json={"name": "X"})).status_code == 403
        assert (await ac.get(f"/api/v1/members/{member.id}/functions")).status_code == 403
        assert (await _assign(ac, member.id, treasurer.id)).status_code == 403


async def test_board_can_assign_but_not_manage_functions(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
    member: Member,
    treasurer: Function,
) -> None:
    client = await _build_client_for(
        db_session, fake_redis, test_user.id, test_tenant.id, role="board"
    )
    async with client as ac:
        assert (await ac.get("/api/v1/functions")).status_code == 200
        assert (await ac.post("/api/v1/functions", json={"name": "X"})).status_code == 403
        assert (await ac.delete(f"/api/v1/functions/{treasurer.id}")).status_code == 403
        assert (await _assign(ac, member.id, treasurer.id)).status_code == 201


async def test_unauthenticated_rejected(anon_client: AsyncClient) -> None:
    assert (await anon_client.get("/api/v1/functions")).status_code == 403
    assert (await anon_client.get("/api/v1/functions/holders")).status_code == 403


# --- Tenant isolation ---


async def test_tenant_isolation(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
) -> None:
    other_tenant = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other_tenant)
    await db_session.flush()
    foreign_function = _function(other_tenant.id, name="Fremdamt")
    foreign_member = _member(other_tenant.id, first_name="Fred", last_name="Fremd")
    db_session.add_all([foreign_function, foreign_member])
    await db_session.flush()
    db_session.add(
        MemberFunction(
            tenant_id=other_tenant.id,
            member_id=foreign_member.id,
            function_id=foreign_function.id,
            valid_from=date(2025, 1, 1),
        )
    )
    await db_session.flush()

    # A's list does not contain B's function, and B's rows are unreachable.
    assert (await auth_client.get("/api/v1/functions")).json()["data"] == []
    assert (await auth_client.get("/api/v1/functions/holders")).json()["data"] == []
    assert (
        await auth_client.patch(
            f"/api/v1/functions/{foreign_function.id}", json={"name": "Hijacked"}
        )
    ).status_code == 404
    assert (
        await auth_client.get(f"/api/v1/members/{foreign_member.id}/functions")
    ).status_code == 404


# --- Onboarding seeding ---


@pytest.fixture
async def catalog(db_session: AsyncSession) -> Sport:
    """A sport plus catalog functions: two general, one division-level, one
    sport-specific, one inactive."""
    sport = Sport(id=uuid.uuid4(), key="shooting", name="Schießsport", is_active=True, modules=[])
    db_session.add(sport)
    await db_session.flush()
    db_session.add_all(
        [
            CatalogFunction(
                key="chairperson", name="1. Vorsitzende:r", level="club", sort_order=10
            ),
            CatalogFunction(
                key="treasurer",
                name="Kassier",
                level="club",
                suggested_role="board",
                sort_order=20,
            ),
            CatalogFunction(
                key="division_leader",
                name="Abteilungsleiter:in",
                level="division",
                sort_order=30,
            ),
            CatalogFunction(
                key="shooting_master",
                name="Schützenmeister",
                level="club",
                sport_id=sport.id,
                sort_order=40,
            ),
            CatalogFunction(
                key="old_office", name="Altamt", level="club", sort_order=50, is_active=False
            ),
        ]
    )
    await db_session.flush()
    return sport


async def _created_function_names(db_session: AsyncSession, slug: str) -> list[str]:
    tenant_id = (
        await db_session.execute(select(Tenant.id).where(Tenant.slug == slug))
    ).scalar_one()
    result = await db_session.execute(
        select(Function.name).where(Function.tenant_id == tenant_id).order_by(Function.sort_order)
    )
    return list(result.scalars().all())


async def test_onboarding_seeds_functions_without_divisions(
    onboarding_client: AsyncClient, db_session: AsyncSession, catalog: Sport
) -> None:
    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club",
        json={
            "club_name": "SV Seed",
            "has_divisions": False,
            "divisions": [{"name": "SV Seed", "sport_key": "shooting"}],
        },
    )
    assert response.status_code == 200
    names = await _created_function_names(db_session, response.json()["data"]["slug"])
    # Division-level and inactive offices are skipped, sport offices included.
    assert names == ["1. Vorsitzende:r", "Kassier", "Schützenmeister"]


async def test_onboarding_seeds_division_functions_with_divisions(
    onboarding_client: AsyncClient, db_session: AsyncSession, catalog: Sport
) -> None:
    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club",
        json={
            "club_name": "SV Sparten",
            "has_divisions": True,
            "divisions": [{"name": "Pistole", "sport_key": "shooting"}],
        },
    )
    assert response.status_code == 200
    names = await _created_function_names(db_session, response.json()["data"]["slug"])
    assert "Abteilungsleiter:in" in names


async def test_onboarding_respects_function_keys_subset(
    onboarding_client: AsyncClient, db_session: AsyncSession, catalog: Sport
) -> None:
    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club",
        json={
            "club_name": "SV Auswahl",
            "has_divisions": False,
            "divisions": [{"name": "SV Auswahl", "sport_key": "shooting"}],
            "function_keys": ["treasurer", "unknown_key"],
        },
    )
    assert response.status_code == 200
    names = await _created_function_names(db_session, response.json()["data"]["slug"])
    assert names == ["Kassier"]


async def test_seeded_suggested_role_is_copied(
    onboarding_client: AsyncClient, db_session: AsyncSession, catalog: Sport
) -> None:
    response = await onboarding_client.post(
        "/api/v1/auth/onboarding/create-club",
        json={
            "club_name": "SV Rollen",
            "has_divisions": False,
            "divisions": [{"name": "SV Rollen", "sport_key": "shooting"}],
            "function_keys": ["treasurer"],
        },
    )
    assert response.status_code == 200
    tenant_id = (
        await db_session.execute(
            select(Tenant.id).where(Tenant.slug == response.json()["data"]["slug"])
        )
    ).scalar_one()
    function = (
        await db_session.execute(select(Function).where(Function.tenant_id == tenant_id))
    ).scalar_one()
    assert function.suggested_role == "board"


# --- Club divisions listing (support for the division picker) ---


async def test_list_club_divisions(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    db_session.add_all(
        [
            Division(tenant_id=test_tenant.id, name="Bogen", is_primary=False),
            Division(tenant_id=test_tenant.id, name="Pistole", is_primary=True),
        ]
    )
    await db_session.flush()

    response = await auth_client.get("/api/v1/club/divisions")
    assert response.status_code == 200
    data = response.json()["data"]
    # Primary first, then alphabetical.
    assert [d["name"] for d in data] == ["Pistole", "Bogen"]
