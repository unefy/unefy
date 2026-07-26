"""Tests for the generic events API: CRUD, registration, waitlist, tenant scope."""

import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member import Member
from app.models.tenant import Tenant


async def _add_member(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    member_number: str,
) -> Member:
    member = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_number=member_number,
        first_name="Alice",
        last_name="Example",
        joined_at=date(2024, 1, 1),
        status="active",
    )
    session.add(member)
    await session.flush()
    return member


async def _create_event(client: AsyncClient, **overrides: object) -> dict:
    payload: dict = {
        "title": "Vereinsmeisterschaft",
        "event_type": "competition",
        "starts_at": "2026-09-01T10:00:00+00:00",
        **overrides,
    }
    resp = await client.post("/api/v1/events", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# --- CRUD ---


async def test_create_and_list_events(auth_client: AsyncClient) -> None:
    created = await _create_event(auth_client)
    assert created["title"] == "Vereinsmeisterschaft"
    assert created["status"] == "scheduled"
    assert created["registered_count"] == 0

    resp = await auth_client.get("/api/v1/events")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


async def test_create_event_invalid_times(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/v1/events",
        json={
            "title": "X",
            "starts_at": "2026-09-01T10:00:00+00:00",
            "ends_at": "2026-09-01T08:00:00+00:00",
        },
    )
    assert resp.status_code == 422


async def test_update_event(auth_client: AsyncClient) -> None:
    created = await _create_event(auth_client)
    resp = await auth_client.patch(
        f"/api/v1/events/{created['id']}",
        json={"title": "Neuer Titel", "status": "cancelled"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "Neuer Titel"
    assert resp.json()["data"]["status"] == "cancelled"


async def test_delete_event(auth_client: AsyncClient) -> None:
    created = await _create_event(auth_client)
    resp = await auth_client.delete(f"/api/v1/events/{created['id']}")
    assert resp.status_code == 204
    resp = await auth_client.get(f"/api/v1/events/{created['id']}")
    assert resp.status_code == 404


async def test_list_events_filters_by_time(auth_client: AsyncClient) -> None:
    await _create_event(auth_client, starts_at="2026-01-15T10:00:00+00:00")
    await _create_event(auth_client, title="Später", starts_at="2026-10-15T10:00:00+00:00")

    resp = await auth_client.get("/api/v1/events?starts_after=2026-06-01T00:00:00%2B00:00")
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "Später"


async def test_events_require_auth(anon_client: AsyncClient) -> None:
    resp = await anon_client.get("/api/v1/events")
    assert resp.status_code == 403


# --- Registrations ---


async def test_register_member(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    event = await _create_event(auth_client)
    member = await _add_member(db_session, test_tenant.id, member_number="M-001")

    resp = await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(member.id)},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["status"] == "registered"

    resp = await auth_client.get(f"/api/v1/events/{event['id']}")
    data = resp.json()["data"]
    assert data["registered_count"] == 1
    assert data["registrations"][0]["member_name"] == "Alice Example"


async def test_register_member_twice_conflict(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    event = await _create_event(auth_client)
    member = await _add_member(db_session, test_tenant.id, member_number="M-001")

    await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(member.id)},
    )
    resp = await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(member.id)},
    )
    assert resp.status_code == 409


async def test_registration_waitlist_when_full(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    event = await _create_event(auth_client, max_participants=1)
    m1 = await _add_member(db_session, test_tenant.id, member_number="M-001")
    m2 = await _add_member(db_session, test_tenant.id, member_number="M-002")

    resp = await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(m1.id)},
    )
    assert resp.json()["data"]["status"] == "registered"

    resp = await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(m2.id)},
    )
    assert resp.json()["data"]["status"] == "waitlist"


async def test_unregister_promotes_waitlist(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    event = await _create_event(auth_client, max_participants=1)
    m1 = await _add_member(db_session, test_tenant.id, member_number="M-001")
    m2 = await _add_member(db_session, test_tenant.id, member_number="M-002")

    resp = await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(m1.id)},
    )
    reg1_id = resp.json()["data"]["id"]
    await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(m2.id)},
    )

    resp = await auth_client.delete(f"/api/v1/events/{event['id']}/registrations/{reg1_id}")
    assert resp.status_code == 204

    resp = await auth_client.get(f"/api/v1/events/{event['id']}")
    data = resp.json()["data"]
    assert len(data["registrations"]) == 1
    assert data["registrations"][0]["status"] == "registered"
    assert data["registrations"][0]["member_id"] == str(m2.id)


async def test_register_on_cancelled_event_conflict(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    event = await _create_event(auth_client)
    await auth_client.patch(f"/api/v1/events/{event['id']}", json={"status": "cancelled"})
    member = await _add_member(db_session, test_tenant.id, member_number="M-001")

    resp = await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(member.id)},
    )
    assert resp.status_code == 409


async def test_register_after_deadline_conflict(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    event = await _create_event(auth_client, registration_deadline="2020-01-01T00:00:00+00:00")
    member = await _add_member(db_session, test_tenant.id, member_number="M-001")

    resp = await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(member.id)},
    )
    assert resp.status_code == 409


async def test_register_unknown_member_not_found(auth_client: AsyncClient) -> None:
    event = await _create_event(auth_client)
    resp = await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


# --- Competition/Session link ---


async def _create_competition_with_session(
    client: AsyncClient, name: str = "Liga 2026"
) -> tuple[dict, dict]:
    resp = await client.post(
        "/api/v1/competitions",
        json={"name": name, "start_date": "2026-06-01"},
    )
    assert resp.status_code == 200, resp.text
    comp = resp.json()["data"]
    resp = await client.post(
        f"/api/v1/competitions/{comp['id']}/sessions",
        json={"date": "2026-06-15", "name": "Runde 1", "location": "Schießstand"},
    )
    assert resp.status_code == 200, resp.text
    return comp, resp.json()["data"]


async def test_event_with_session_link_sets_type_and_competition(
    auth_client: AsyncClient,
) -> None:
    comp, sess = await _create_competition_with_session(auth_client)
    created = await _create_event(auth_client, event_type="other", session_id=sess["id"])
    assert created["session_id"] == sess["id"]
    assert created["competition_id"] == comp["id"]  # derived from session
    assert created["event_type"] == "competition"
    assert created["competition_name"] == "Liga 2026"

    resp = await auth_client.get(f"/api/v1/events/{created['id']}")
    assert resp.json()["data"]["competition_name"] == "Liga 2026"

    resp = await auth_client.get("/api/v1/events")
    assert resp.json()["data"][0]["competition_name"] == "Liga 2026"


async def test_event_with_competition_link_only(auth_client: AsyncClient) -> None:
    comp, _sess = await _create_competition_with_session(auth_client)
    created = await _create_event(auth_client, event_type="other", competition_id=comp["id"])
    assert created["event_type"] == "competition"
    assert created["session_id"] is None


async def test_event_with_session_from_other_competition_422(
    auth_client: AsyncClient,
) -> None:
    _comp_a, sess_a = await _create_competition_with_session(auth_client, name="Liga A")
    resp = await auth_client.post(
        "/api/v1/competitions",
        json={"name": "Liga B", "start_date": "2026-06-01"},
    )
    comp_b = resp.json()["data"]

    resp = await auth_client.post(
        "/api/v1/events",
        json={
            "title": "X",
            "starts_at": "2026-09-01T10:00:00+00:00",
            "competition_id": comp_b["id"],
            "session_id": sess_a["id"],
        },
    )
    assert resp.status_code == 422


async def test_event_with_unknown_session_404(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/v1/events",
        json={
            "title": "X",
            "starts_at": "2026-09-01T10:00:00+00:00",
            "session_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 404


async def test_event_update_can_set_session_link(auth_client: AsyncClient) -> None:
    comp, sess = await _create_competition_with_session(auth_client)
    created = await _create_event(auth_client, event_type="other")
    resp = await auth_client.patch(
        f"/api/v1/events/{created['id']}",
        json={"session_id": sess["id"]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["competition_id"] == comp["id"]
    assert data["event_type"] == "competition"
