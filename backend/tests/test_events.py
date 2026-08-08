"""Tests for the generic events API: CRUD, registration, waitlist, tenant scope."""

import uuid
from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import User


async def _add_member(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    member_number: str,
    user_id: uuid.UUID | None = None,
) -> Member:
    member = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_number=member_number,
        user_id=user_id,
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


async def test_get_event_reports_own_registration(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The detail answers "am I on this event" like the list does — any status."""
    event = await _create_event(auth_client)
    own = await _add_member(db_session, test_tenant.id, member_number="M-001", user_id=test_user.id)
    other = await _add_member(db_session, test_tenant.id, member_number="M-002")

    resp = await auth_client.get(f"/api/v1/events/{event['id']}")
    assert resp.json()["data"]["is_registered"] is False

    resp = await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(other.id)},
    )
    assert resp.status_code == 201
    resp = await auth_client.get(f"/api/v1/events/{event['id']}")
    assert resp.json()["data"]["is_registered"] is False

    resp = await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(own.id)},
    )
    assert resp.status_code == 201
    resp = await auth_client.get(f"/api/v1/events/{event['id']}")
    assert resp.json()["data"]["is_registered"] is True


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


async def test_reregister_after_cancellation(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """Unregistering soft-deletes the row; signing up again must revive it.

    The unique constraint (tenant, event, member) covers soft-deleted rows,
    so a naive re-insert was an IntegrityError — a 500 on the second sign-up.
    """
    event = await _create_event(auth_client)
    member = await _add_member(db_session, test_tenant.id, member_number="M-001")

    resp = await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(member.id)},
    )
    assert resp.status_code == 201
    registration_id = resp.json()["data"]["id"]

    resp = await auth_client.delete(f"/api/v1/events/{event['id']}/registrations/{registration_id}")
    assert resp.status_code == 204

    resp = await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(member.id)},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["status"] == "registered"

    resp = await auth_client.get(f"/api/v1/events/{event['id']}")
    data = resp.json()["data"]
    assert data["registered_count"] == 1
    assert len(data["registrations"]) == 1


async def test_register_after_deadline(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The deadline binds self-registration; the board adds people past it."""
    event = await _create_event(auth_client, registration_deadline="2020-01-01T00:00:00+00:00")
    member = await _add_member(db_session, test_tenant.id, member_number="M-001")
    await _add_member(db_session, test_tenant.id, member_number="M-002", user_id=test_user.id)

    resp = await auth_client.post(f"/api/v1/events/{event['id']}/registrations/me")
    assert resp.status_code == 409

    resp = await auth_client.post(
        f"/api/v1/events/{event['id']}/registrations",
        json={"member_id": str(member.id)},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["status"] == "registered"


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


async def test_list_events_filters_by_competition(auth_client: AsyncClient) -> None:
    comp, _sess = await _create_competition_with_session(auth_client)
    await _create_event(auth_client, title="Ohne Liga")
    linked = await _create_event(auth_client, title="Mit Liga", competition_id=comp["id"])

    resp = await auth_client.get(f"/api/v1/events?competition_id={comp['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 1
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == linked["id"]


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


# --- Termin ↔ Einheit (attendance link) ---


async def _member_client(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> AsyncClient:
    """A client whose session carries the plain "member" role."""
    import json

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
        json.dumps({"user_id": str(user_id), "tenant_id": str(tenant_id), "role": "member"}),
        ex=604800,
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": token},
    )


async def test_attendance_session_accepts_a_valid_event_link(auth_client: AsyncClient) -> None:
    event = await _create_event(auth_client, title="Übungsabend")
    resp = await auth_client.post(
        "/api/v1/attendance/sessions",
        json={
            "title": "Stand 1",
            "opens_at": "2026-09-01T10:00:00+00:00",
            "closes_at": "2026-09-01T14:00:00+00:00",
            "event_id": event["id"],
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["event_id"] == event["id"]
    assert data["event_title"] == "Übungsabend"

    # The list carries the title too — the scanner's chips show it.
    resp = await auth_client.get("/api/v1/attendance/sessions")
    row = next(r for r in resp.json()["data"] if r["id"] == data["id"])
    assert row["event_title"] == "Übungsabend"


async def test_attendance_session_rejects_an_unknown_event(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/v1/attendance/sessions",
        json={
            "title": "Stand 1",
            "opens_at": "2026-09-01T10:00:00+00:00",
            "closes_at": "2026-09-01T14:00:00+00:00",
            "event_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 404


async def test_attendance_session_rejects_an_event_of_another_tenant(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    from datetime import UTC, datetime

    from app.models.event import Event
    from app.models.tenant import Tenant as TenantModel

    other = TenantModel(id=uuid.uuid4(), name="Other Club", slug="other-club-events")
    db_session.add(other)
    await db_session.flush()
    foreign = Event(
        tenant_id=other.id,
        title="Fremder Abend",
        starts_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
    )
    db_session.add(foreign)
    await db_session.flush()

    resp = await auth_client.post(
        "/api/v1/attendance/sessions",
        json={
            "title": "Stand 1",
            "opens_at": "2026-09-01T10:00:00+00:00",
            "closes_at": "2026-09-01T14:00:00+00:00",
            "event_id": str(foreign.id),
        },
    )
    assert resp.status_code == 404


async def test_attendance_session_update_validates_the_event(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/v1/attendance/sessions",
        json={
            "title": "Stand 1",
            "opens_at": "2026-09-01T10:00:00+00:00",
            "closes_at": "2026-09-01T14:00:00+00:00",
        },
    )
    session_id = resp.json()["data"]["id"]

    resp = await auth_client.patch(
        f"/api/v1/attendance/sessions/{session_id}",
        json={"event_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404

    event = await _create_event(auth_client, title="Übungsabend")
    resp = await auth_client.patch(
        f"/api/v1/attendance/sessions/{session_id}",
        json={"event_id": event["id"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["event_title"] == "Übungsabend"


async def test_open_attendance_session_from_event(auth_client: AsyncClient) -> None:
    event = await _create_event(
        auth_client,
        title="Übungsabend",
        location="Stand West",
        starts_at="2026-09-01T17:00:00+00:00",
        ends_at="2026-09-01T21:00:00+00:00",
    )
    resp = await auth_client.post(f"/api/v1/events/{event['id']}/attendance-session")
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["title"] == "Übungsabend"
    assert data["location"] == "Stand West"
    assert data["event_id"] == event["id"]
    assert data["status"] == "open"
    assert data["opens_at"] == "2026-09-01T17:00:00Z"
    assert data["closes_at"] == "2026-09-01T21:00:00Z"


async def test_open_attendance_session_is_idempotent(auth_client: AsyncClient) -> None:
    event = await _create_event(auth_client, title="Übungsabend")
    first = await auth_client.post(f"/api/v1/events/{event['id']}/attendance-session")
    assert first.status_code == 201

    second = await auth_client.post(f"/api/v1/events/{event['id']}/attendance-session")
    assert second.status_code == 200
    assert second.json()["data"]["id"] == first.json()["data"]["id"]


async def test_open_attendance_session_defaults_the_window(auth_client: AsyncClient) -> None:
    """No end on the event → the scanner's eight hours, closing stays deliberate."""
    event = await _create_event(auth_client, starts_at="2026-09-01T17:00:00+00:00")
    resp = await auth_client.post(f"/api/v1/events/{event['id']}/attendance-session")
    assert resp.status_code == 201
    assert resp.json()["data"]["closes_at"] == "2026-09-02T01:00:00Z"


async def test_open_attendance_session_for_unknown_event(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(f"/api/v1/events/{uuid.uuid4()}/attendance-session")
    assert resp.status_code == 404


async def test_open_attendance_session_requires_board(
    anon_client: AsyncClient,
    auth_client: AsyncClient,
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
) -> None:
    event = await _create_event(auth_client)

    resp = await anon_client.post(f"/api/v1/events/{event['id']}/attendance-session")
    assert resp.status_code == 403

    member_client = await _member_client(db_session, fake_redis, test_user.id, test_tenant.id)
    resp = await member_client.post(f"/api/v1/events/{event['id']}/attendance-session")
    assert resp.status_code == 403
    await member_client.aclose()


async def test_event_detail_embeds_attendance_sessions_for_board(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    # An event happening now: the session it opens inherits its window, and a
    # check-in has to fall on the session's own evening.
    event = await _create_event(
        auth_client,
        title="Übungsabend",
        starts_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat(),
    )
    opened = await auth_client.post(f"/api/v1/events/{event['id']}/attendance-session")
    session_id = opened.json()["data"]["id"]

    member = await _add_member(db_session, test_tenant.id, member_number="M-100")
    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{session_id}/check-in",
        json={"member_id": str(member.id)},
    )
    assert resp.status_code == 201

    resp = await auth_client.get(f"/api/v1/events/{event['id']}")
    sessions = resp.json()["data"]["attendance_sessions"]
    assert [s["id"] for s in sessions] == [session_id]
    assert sessions[0]["record_count"] == 1
    assert sessions[0]["status"] == "open"


async def test_event_detail_hides_attendance_from_members(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """Attendance is the board's record; the calendar must not leak it."""
    event = await _create_event(auth_client)
    await auth_client.post(f"/api/v1/events/{event['id']}/attendance-session")

    member_client = await _member_client(db_session, fake_redis, test_user.id, test_tenant.id)
    resp = await member_client.get(f"/api/v1/events/{event['id']}")
    assert resp.status_code == 200
    assert resp.json()["data"]["attendance_sessions"] == []
    await member_client.aclose()
