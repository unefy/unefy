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
from app.events.outbox import take_pending
from app.models.attendance import AttendanceCheckinContext, AttendanceRecord
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import User
from app.services.attendance import CHECK_IN_SIGNAL
from app.services.attendance_code import (
    build_code,
    counter_for,
    derive_seed,
    new_member_ref,
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


async def _seed_of(
    session: AsyncSession, tenant_id: uuid.UUID, member: Member, at: int | None = None
) -> dict:
    """Somebody else's seed, minted directly.

    `/me/seed` only ever answers for the caller, and most of what happens here is
    a supervisor scanning a *different* person — the only scan that proves
    anything. Deriving the seed the way the endpoint would is what lets a test
    build that other person's code.
    """
    if member.attendance_ref is None:
        member.attendance_ref = new_member_ref()
        await session.flush()
    moment = at if at is not None else _now()
    return {
        "member_ref": member.attendance_ref,
        "seed": derive_seed(
            get_settings().ATTENDANCE_SECRET, tenant_id, member.id, seed_period(moment)
        ),
    }


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


# --- Self-entries ---


async def test_the_supervisor_ticking_themselves_off_is_marked_as_a_self_entry(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """Who checks in the supervisor? They do, and it has to say so.

    Only the board may create check-ins, and a supervisor alone at the range has
    no other route to their own attendance — a QR needs two devices and theirs is
    the reader. So this is allowed. What must not happen is that it looks like a
    record somebody else vouched for: the people who can create records at will
    are exactly the people such a record would flatter.
    """
    member = await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"member_id": str(member.id)},
    )

    assert resp.status_code == 201, resp.text
    record = resp.json()["data"]
    assert record["method"] == "self"
    assert record["assurance"] == "low"


async def test_scanning_ones_own_code_is_a_self_entry_too(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """Reachable by putting one's own code on a second screen — and worth nothing.

    The signature verifies, so without this the record would come out as
    `staff_scan`/`high`: the strongest evidence in the system, produced alone. The
    cryptography proves which device the code came from and no more; whoever holds
    both ends of the scan has attested nothing to anybody.
    """
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
    assert record["method"] == "self"
    assert record["assurance"] == "low"


async def test_ticking_somebody_else_off_stays_a_manual_check_in(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    # The marker has to be specific, or it says nothing. A board member ticking
    # off a member is somebody vouching for somebody else, however weakly.
    await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    other = await _add_member(db_session, test_tenant.id, member_number="002")
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"member_id": str(other.id)},
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["method"] == "manual"


async def test_a_member_with_their_own_account_is_not_a_self_entry(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """The discriminating case: an app-using member, ticked off by the supervisor.

    Two accounts are involved, which is what makes this the test that can tell
    "the subject is the author" apart from "an account exists somewhere". Both
    neighbouring tests use members without accounts and would pass even if every
    check-in were marked as a self-entry.
    """
    await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    other_account = User(
        id=uuid.uuid4(),
        email="erika@example.org",
        name="Erika Beispiel",
        image=None,
        email_verified=True,
    )
    db_session.add(other_account)
    await db_session.flush()
    other = await _add_member(
        db_session, test_tenant.id, member_number="004", user_id=other_account.id
    )
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"member_id": str(other.id)},
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["method"] == "manual"


async def test_a_member_without_an_account_is_never_a_self_entry(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    # Nothing to compare the caller against. The guard matters because an
    # unlinked member is the common case, not the exception.
    member = await _add_member(db_session, test_tenant.id, member_number="003")
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"member_id": str(member.id)},
    )

    assert resp.json()["data"]["method"] == "manual"


# --- The member's own device ---


async def test_a_check_in_is_announced_to_the_members_own_device(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """The hole two devices revealed: the check-in happens on somebody else's phone.

    The scanner learns the outcome from its own response. The member's phone is
    holding up a code and has no way to find out that the code was taken, so it is
    told — addressed to that member's account, because one stream serves the whole
    club and who was present is nobody else's business.
    """
    member = await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    seed = await _seed_for(auth_client)
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan",
        json={"code": _current_code(seed["seed"], seed["member_ref"], test_tenant.id, _now())},
    )
    assert resp.status_code == 201, resp.text

    hint = next(e for e in take_pending(db_session) if e.entity == CHECK_IN_SIGNAL)
    assert str(hint.entity_id) == resp.json()["data"]["id"]
    assert hint.audience_user_id == test_user.id
    assert hint.op == "upsert"
    assert member.user_id == test_user.id


async def test_a_removal_is_announced_too(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """Otherwise a confirmed screen would outlive the record behind it.

    A supervisor who takes a check-in back leaves the member looking at a green
    tick the server no longer stands behind.
    """
    await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    seed = await _seed_for(auth_client)
    created = await _create_session(auth_client)
    scan = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan",
        json={"code": _current_code(seed["seed"], seed["member_ref"], test_tenant.id, _now())},
    )
    record_id = scan.json()["data"]["id"]
    take_pending(db_session)

    resp = await auth_client.delete(f"/api/v1/attendance/records/{record_id}")
    assert resp.status_code == 204, resp.text

    hint = next(e for e in take_pending(db_session) if e.entity == CHECK_IN_SIGNAL)
    assert str(hint.entity_id) == record_id
    assert hint.audience_user_id == test_user.id
    assert hint.op == "delete"


async def test_the_announcement_goes_to_the_member_not_to_the_supervisor(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """The distinction the other tests cannot make.

    Everywhere else here the signed-in account happens to be the member's own, so
    "addressed to the member" and "addressed to the caller" look identical. In
    reality they are never the same person: the supervisor ticks somebody else off
    a list, and a frame addressed to the supervisor would confirm a check-in on the
    wrong phone while leaving the right one waiting.
    """
    other = User(
        id=uuid.uuid4(),
        email="erika@example.org",
        name="Erika Beispiel",
        image=None,
        email_verified=True,
    )
    db_session.add(other)
    await db_session.flush()
    member = await _add_member(db_session, test_tenant.id, member_number="003", user_id=other.id)
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"member_id": str(member.id)},
    )
    assert resp.status_code == 201, resp.text

    hint = next(e for e in take_pending(db_session) if e.entity == CHECK_IN_SIGNAL)
    assert hint.audience_user_id == other.id


async def test_a_member_without_an_account_is_not_announced_to(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """There is no device to tell.

    Most members of most clubs will never install the app, and their check-ins
    must not put frames on the stream addressed to nobody.
    """
    member = await _add_member(db_session, test_tenant.id, member_number="002")
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"member_id": str(member.id)},
    )
    assert resp.status_code == 201, resp.text

    assert [e for e in take_pending(db_session) if e.entity == CHECK_IN_SIGNAL] == []


async def test_a_guest_is_not_announced_to(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    # A guest has no member row at all, so there is nothing to resolve an
    # account from — and the code path must not try.
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"guest_name": "Jonas Gast"},
    )
    assert resp.status_code == 201, resp.text

    assert [e for e in take_pending(db_session) if e.entity == CHECK_IN_SIGNAL] == []


# --- Scanned check-in ---


async def test_scan_creates_a_high_assurance_record(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """A supervisor scanning *somebody else* — the only scan that attests anything.

    The member is deliberately not the signed-in account: a scan of one's own code
    is a self-entry and recorded as one, see the test below.
    """
    member = await _add_member(db_session, test_tenant.id)
    seed = await _seed_of(db_session, test_tenant.id, member)
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


# --- Buffered check-in (offline queue) ---


async def test_buffered_scan_is_verified_against_the_moment_it_claims(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """The whole point of the queue: a code read offline is stale by now.

    Checked against the claimed moment instead, so a scan taken in a basement
    and synced afterwards still verifies — while the claim itself stays bounded
    by the session window.
    """
    member = await _add_member(db_session, test_tenant.id)
    created = await _create_session(auth_client)

    # An hour into the session, which was weeks ago — far outside the drift a
    # live scan is allowed.
    scanned_at = datetime(2026, 7, 7, 18, 0, tzinfo=UTC)
    at = int(scanned_at.timestamp())
    seed_data = await _seed_of(db_session, test_tenant.id, member, at)
    code = build_code(seed_data["seed"], seed_data["member_ref"], test_tenant.id, counter_for(at))

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan",
        json={"code": code, "checked_in_at": scanned_at.isoformat()},
    )

    assert resp.status_code == 201, resp.text
    record = resp.json()["data"]
    assert record["checked_in_at"].startswith("2026-07-07T18:00")
    # Both facts kept apart: when it happened, and when it reached us.
    assert record["synced_at"] is not None
    assert record["assurance"] == "high"


async def test_same_code_without_the_claim_is_too_old(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    # The counterpart to the test above: nothing was loosened for live scans.
    member = await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    seed_data = await _seed_for(auth_client)
    created = await _create_session(auth_client)

    at = int(datetime(2026, 7, 7, 18, 0, tzinfo=UTC).timestamp())
    seed = derive_seed(get_settings().ATTENDANCE_SECRET, test_tenant.id, member.id, seed_period(at))
    code = build_code(seed, seed_data["member_ref"], test_tenant.id, counter_for(at))

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/scan", json={"code": code}
    )
    assert resp.status_code == 422, resp.text


async def test_buffered_manual_check_in_keeps_both_times(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    member = await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={
            "member_id": str(member.id),
            "checked_in_at": "2026-07-07T18:30:00+00:00",
        },
    )

    assert resp.status_code == 201, resp.text
    record = resp.json()["data"]
    assert record["checked_in_at"].startswith("2026-07-07T18:30")
    assert record["synced_at"] is not None


async def test_a_live_check_in_is_not_marked_as_synced(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    # No claim means nothing was buffered, and the record must not suggest it.
    member = await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"member_id": str(member.id)},
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["synced_at"] is None


@pytest.mark.parametrize(
    ("claimed", "reason"),
    [
        ("2099-01-01T12:00:00+00:00", "future"),
        ("2026-07-07T16:00:00+00:00", "before the session opened"),
    ],
)
async def test_an_out_of_range_device_time_is_refused(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
    claimed: str,
    reason: str,
) -> None:
    """A device clock is a claim, not evidence.

    Unbounded, it would be a way around the freeze on closed sessions: backdate
    someone into an evening they were not at.
    """
    member = await _add_member(db_session, test_tenant.id, user_id=test_user.id)
    created = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{created['id']}/check-in",
        json={"member_id": str(member.id), "checked_in_at": claimed},
    )

    assert resp.status_code == 422, f"{reason}: {resp.text}"
