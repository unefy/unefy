"""Client-supplied ids on member and event creation.

The mobile app queues writes on a range with no signal and drains the queue
whenever the network comes back. What it cannot know is whether a request it
never got an answer to was lost on the way out or on the way back — so it has
to be safe to simply ask again. That is what these tests pin down: the same id
twice yields one record, not two.

The equivalent for recorded series already exists (`create_idempotent` in
`repositories/competition.py`); this is the same contract for the two entities
the app can now create.
"""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models.event import Event
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User

STARTS_AT = datetime(2026, 9, 1, 18, 0, tzinfo=UTC)


async def _client_for(
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
        json.dumps({"user_id": str(user_id), "tenant_id": str(tenant_id), "role": "owner"}),
        ex=604800,
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": token},
    )


def _member_payload(member_id: uuid.UUID) -> dict[str, str]:
    return {"id": str(member_id), "first_name": "Ida", "last_name": "Beispiel"}


def _event_payload(event_id: uuid.UUID) -> dict[str, str]:
    return {
        "id": str(event_id),
        "title": "Vereinsabend",
        "starts_at": STARTS_AT.isoformat(),
    }


# --- Members ---


async def test_replaying_a_member_creation_does_not_create_a_second_member(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """The whole point: a retried request is answered, not obeyed twice."""
    member_id = uuid.uuid4()

    client = await _client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        first = await ac.post("/api/v1/members", json=_member_payload(member_id))
        second = await ac.post("/api/v1/members", json=_member_payload(member_id))

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["data"]["id"] == str(member_id)
    # Same record, member number included — the second call must not have
    # allocated a new one.
    assert second.json()["data"]["id"] == str(member_id)
    assert second.json()["data"]["member_number"] == first.json()["data"]["member_number"]

    count = await db_session.scalar(
        select(func.count()).select_from(Member).where(Member.tenant_id == test_tenant.id)
    )
    assert count == 1


async def test_member_creation_without_an_id_still_works(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """The web app sends no id, and two such calls are two members."""
    client = await _client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        first = await ac.post(
            "/api/v1/members", json={"first_name": "Ida", "last_name": "Beispiel"}
        )
        second = await ac.post(
            "/api/v1/members", json={"first_name": "Ida", "last_name": "Beispiel"}
        )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["data"]["id"] != second.json()["data"]["id"]

    count = await db_session.scalar(
        select(func.count()).select_from(Member).where(Member.tenant_id == test_tenant.id)
    )
    assert count == 2


async def test_a_member_id_belonging_to_another_club_is_refused(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """409, not 500 — and above all not the other club's member back.

    The replay lookup is tenant-scoped and finds nothing; the primary key is
    global and collides. Without this branch that combination reached the
    client as an unhandled error.
    """
    foreign_tenant = Tenant(id=uuid.uuid4(), name="Other", slug="other-club")
    db_session.add(foreign_tenant)
    await db_session.flush()
    foreign_member = Member(
        id=uuid.uuid4(),
        tenant_id=foreign_tenant.id,
        member_number="999",
        first_name="Fremd",
        last_name="Person",
    )
    db_session.add(foreign_member)
    await db_session.flush()

    client = await _client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        resp = await ac.post("/api/v1/members", json=_member_payload(foreign_member.id))

    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "ID_IN_USE"
    # And nothing of the other club's leaked into the answer.
    assert "Fremd" not in resp.text


# --- Events ---


async def test_replaying_an_event_creation_does_not_create_a_second_event(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    event_id = uuid.uuid4()

    client = await _client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        first = await ac.post("/api/v1/events", json=_event_payload(event_id))
        second = await ac.post("/api/v1/events", json=_event_payload(event_id))

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["data"]["id"] == str(event_id)
    assert second.json()["data"]["id"] == str(event_id)

    count = await db_session.scalar(
        select(func.count()).select_from(Event).where(Event.tenant_id == test_tenant.id)
    )
    assert count == 1


async def test_an_event_id_belonging_to_another_club_is_refused(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    foreign_tenant = Tenant(id=uuid.uuid4(), name="Other", slug="other-club")
    db_session.add(foreign_tenant)
    await db_session.flush()
    foreign_event = Event(
        id=uuid.uuid4(),
        tenant_id=foreign_tenant.id,
        title="Fremder Termin",
        starts_at=STARTS_AT,
    )
    db_session.add(foreign_event)
    await db_session.flush()

    client = await _client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        resp = await ac.post("/api/v1/events", json=_event_payload(foreign_event.id))

    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "ID_IN_USE"
    assert "Fremder Termin" not in resp.text
