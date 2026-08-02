"""Tests for the scanned check-in: seed handout, staff_scan, replay, tenant scope.

The code arithmetic itself is covered in `test_attendance_code`. What is tested
here is the wiring around it — that a seed reaches the right member, that a
scanned code produces a `high`-assurance record with a context row, and that the
paths which must fail do fail through the API.
"""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db_session
from app.models.attendance import AttendanceCheckinContext, AttendanceRecord
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import User
from app.services.attendance_code import (
    build_code,
    counter_for,
    derive_seed,
    seed_period,
)

OPENS_AT = "2026-07-07T17:00:00+00:00"
CLOSES_AT = "2026-07-07T21:00:00+00:00"


async def _add_member(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    member_number: str = "001",
    user_id: uuid.UUID | None = None,
) -> Member:
    member = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_number=member_number,
        first_name="Alice",
        last_name="Example",
        joined_at=date(2024, 1, 1),
        status="active",
        user_id=user_id,
    )
    session.add(member)
    await session.flush()
    return member


async def _create_session(client: AsyncClient, **overrides: object) -> dict:
    payload: dict = {
        "title": "Übungsabend",
        "opens_at": OPENS_AT,
        "closes_at": CLOSES_AT,
        **overrides,
    }
    resp = await client.post("/api/v1/attendance/sessions", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _client_as(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str = "member",
) -> AsyncClient:
    """A client whose session carries an explicit role — "member" by default."""
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


def _current_code(seed: str, member_ref: str, tenant_id: uuid.UUID, now: int) -> str:
    return build_code(seed, member_ref, tenant_id, counter_for(now))


async def _seed_for(
    client: AsyncClient,
) -> dict:
    resp = await client.get("/api/v1/attendance/me/seed")
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


# --- Seed handout ---


async def test_seed_is_issued_and_mints_a_pseudonym(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    member = await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    assert member.attendance_ref is None

    data = await _seed_for(auth_client)

    assert data["interval_seconds"] == 30
    assert data["algorithm"] == "uf1"
    assert len(data["member_ref"]) == 16
    assert data["seed"]
    # Every input the app needs to build a code, in one response.
    assert data["tenant_id"] == str(test_tenant.id)
    assert data["expires_at"] > 0

    await db_session.refresh(member)
    assert member.attendance_ref == data["member_ref"]


async def test_seed_pseudonym_is_stable_across_calls(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    # A new ref on every call would break every code already on the phone.
    await _add_member(db_session, test_tenant.id, user_id=test_user.id)

    first = await _seed_for(auth_client)
    second = await _seed_for(auth_client)

    assert first["member_ref"] == second["member_ref"]
    assert first["seed"] == second["seed"]


async def test_seed_requires_a_linked_member(auth_client: AsyncClient) -> None:
    # The account exists but no member record hangs off it.
    resp = await auth_client.get("/api/v1/attendance/me/seed")
    assert resp.status_code == 404


async def test_seed_needs_authentication(anon_client: AsyncClient) -> None:
    resp = await anon_client.get("/api/v1/attendance/me/seed")
    assert resp.status_code in (401, 403)


# --- Scanned check-in ---


async def test_scan_creates_a_high_assurance_record(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    member = await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    seed = await _seed_for(auth_client)
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan",
        json={"code": _current_code(seed["seed"], seed["member_ref"], test_tenant.id, _now())},
    )

    assert resp.status_code == 201, resp.text
    record = resp.json()["data"]
    assert record["member_id"] == str(member.id)
    # The point of the whole mechanism: the procedure, not the caller, decides
    # how much the record is worth.
    assert record["method"] == "staff_scan"
    assert record["assurance"] == "high"
    assert record["verified_by_user_id"] == str(test_user.id)
    # The scanner shows this straight back to the supervisor. Without a name,
    # "checked in" tells someone watching a queue nothing.
    assert record["member_name"] == "Alice Example"
    assert record["member_number"] == "001"


async def test_scan_writes_a_context_row_and_a_lasting_digest(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    seed = await _seed_for(auth_client)
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan",
        json={
            "code": _current_code(seed["seed"], seed["member_ref"], test_tenant.id, _now()),
            "install_id": "install-abc",
            "staff_device_id": "scanner-1",
        },
    )
    assert resp.status_code == 201, resp.text

    record = await db_session.get(AttendanceRecord, uuid.UUID(resp.json()["data"]["id"]))
    assert record is not None
    # Survives the context row's deletion — that is the whole design.
    assert record.context_digest is not None
    assert len(record.context_digest) == 64
    assert record.context_verdict == "unchecked"

    context = (
        await db_session.execute(
            select(AttendanceCheckinContext).where(
                AttendanceCheckinContext.attendance_record_id == record.id
            )
        )
    ).scalar_one()
    assert context.install_id == "install-abc"
    assert context.staff_device_id == "scanner-1"
    assert context.code_counter == counter_for(_now())
    # Weeks, not years: the short clock from the retention plan.
    assert context.expires_at is not None


async def test_scan_context_is_optional(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    # A scanner that withholds its identity must not block the check-in — the
    # attendance record is the thing that matters.
    await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    seed = await _seed_for(auth_client)
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan",
        json={"code": _current_code(seed["seed"], seed["member_ref"], test_tenant.id, _now())},
    )
    assert resp.status_code == 201, resp.text


# --- Replay and rejection ---


async def test_the_same_code_cannot_be_used_twice(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """A screenshot passed to a friend must not check anyone in."""
    await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    seed = await _seed_for(auth_client)
    first = await _create_session(auth_client)
    second = await _create_session(auth_client, title="Zweiter Abend")
    code = _current_code(seed["seed"], seed["member_ref"], test_tenant.id, _now())

    assert (
        await auth_client.post(
            f"/api/v1/attendance/sessions/{first['id']}/scan", json={"code": code}
        )
    ).status_code == 201

    # A different session, so the "already checked in" rule cannot be what
    # rejects it — this has to be the replay guard.
    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{second['id']}/scan", json={"code": code}
    )
    assert resp.status_code == 409, resp.text
    # The scanner tells a replayed code apart from a routine duplicate by this
    # code, so it is part of the contract, not an implementation detail.
    assert resp.json()["error"]["code"] == "CODE_ALREADY_USED"


async def test_a_stale_code_is_rejected(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    seed = await _seed_for(auth_client)
    created = await _create_session(auth_client)

    # Ten minutes old: far outside the ±1 counter of accepted drift.
    stale = build_code(seed["seed"], seed["member_ref"], test_tenant.id, counter_for(_now() - 600))

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan", json={"code": stale}
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize(
    "code",
    ["", "nonsense", "uf1.AAAAAAAAAAAAAAAA.1.AAAAAAAAAAAAAAAA"],
)
async def test_unusable_codes_are_rejected(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
    code: str,
) -> None:
    await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan", json={"code": code}
    )
    assert resp.status_code == 422, resp.text


async def test_unknown_pseudonym_is_indistinguishable_from_a_bad_signature(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """The endpoint must not become an oracle for which pseudonyms exist."""
    member = await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    seed = await _seed_for(auth_client)
    created = await _create_session(auth_client)

    settings = get_settings()
    now = _now()
    real_seed = derive_seed(settings.ATTENDANCE_SECRET, test_tenant.id, member.id, seed_period(now))
    # Same member, real seed, but a ref nobody holds.
    unknown = build_code(real_seed, "ZZZZZZZZZZZZZZZZ", test_tenant.id, counter_for(now))
    forged = build_code("not-the-real-seed", seed["member_ref"], test_tenant.id, counter_for(now))

    unknown_resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan", json={"code": unknown}
    )
    forged_resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan", json={"code": forged}
    )

    assert unknown_resp.status_code == forged_resp.status_code == 422
    assert unknown_resp.json()["error"]["message"] == forged_resp.json()["error"]["message"]


async def test_scan_into_a_closed_session_is_refused(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    # Closing freezes the session; a scan is a late entry like any other.
    await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    seed = await _seed_for(auth_client)
    created = await _create_session(auth_client)
    assert (
        await auth_client.post(f"/api/v1/attendance/sessions/{created['id']}/close")
    ).status_code == 200

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan",
        json={"code": _current_code(seed["seed"], seed["member_ref"], test_tenant.id, _now())},
    )
    assert resp.status_code == 409, resp.text


async def test_scanning_twice_into_one_session_is_refused(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    seed = await _seed_for(auth_client)
    created = await _create_session(auth_client)

    first = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan",
        json={"code": _current_code(seed["seed"], seed["member_ref"], test_tenant.id, _now())},
    )
    assert first.status_code == 201

    # A fresh code from the next window: the replay guard cannot be what stops
    # this one, so the duplicate rule has to.
    later = _now() + 30
    second = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan",
        json={"code": _current_code(seed["seed"], seed["member_ref"], test_tenant.id, later)},
    )
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "ALREADY_CHECKED_IN"


async def test_scan_requires_board(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
) -> None:
    # A member may hold a code; they may not run the scanner. The role check has
    # to bite before anything looks at the code.
    client = await _client_as(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        resp = await ac.post(
            f"/api/v1/attendance/sessions/{uuid.uuid4()}/scan", json={"code": "irrelevant"}
        )

    assert resp.status_code == 403


def _now() -> int:
    return int(datetime.now(UTC).timestamp())
