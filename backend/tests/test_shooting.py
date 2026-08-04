"""The shooting module: gating, §14 evaluation, certificates, verify page."""

import hashlib
import json
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.models.attendance import AttendanceRecord, AttendanceSession
from app.models.audit import TenantAuditLog
from app.models.division import Division
from app.models.member import Member
from app.models.shooting import ShootingRecordDetail
from app.models.sport import Sport
from app.models.tenant_sport import TenantSport
from app.models.user import TenantMembership, User

BASE = "/api/v1/modules/shooting"


@pytest.fixture
async def shooting_tenant(db_session: AsyncSession, test_tenant: Tenant) -> Tenant:
    """test_tenant with the shooting module active via its sport."""
    sport = Sport(key=f"shooting-{uuid.uuid4().hex[:6]}", name="Schießsport", modules=["shooting"])
    db_session.add(sport)
    await db_session.flush()
    db_session.add(TenantSport(tenant_id=test_tenant.id, sport_id=sport.id, is_primary=True))
    await db_session.flush()
    return test_tenant


async def _add_member(db_session: AsyncSession, tenant_id: uuid.UUID) -> Member:
    member = Member(
        tenant_id=tenant_id,
        member_number=f"M-{uuid.uuid4().hex[:8]}",
        first_name="Erika",
        last_name="Musterfrau",
    )
    db_session.add(member)
    await db_session.flush()
    return member


async def _add_attendance(
    db_session: AsyncSession,
    tenant_id: uuid.UUID,
    member_id: uuid.UUID | None,
    occurred_on: date,
    *,
    division_id: uuid.UUID | None = None,
    guest_name: str | None = None,
    deleted: bool = False,
    method: str = "manual",
    verified_by_user_id: uuid.UUID | None = None,
) -> AttendanceRecord:
    session = AttendanceSession(
        tenant_id=tenant_id,
        title="Training",
        division_id=division_id,
        opens_at=datetime.combine(occurred_on, datetime.min.time(), tzinfo=UTC),
        closes_at=datetime.combine(occurred_on, datetime.min.time(), tzinfo=UTC)
        + timedelta(hours=3),
    )
    db_session.add(session)
    await db_session.flush()
    record = AttendanceRecord(
        tenant_id=tenant_id,
        session_id=session.id,
        member_id=member_id,
        guest_name=guest_name,
        occurred_on=occurred_on,
        checked_in_at=session.opens_at,
        method=method,
        assurance="low",
        verified_by_user_id=verified_by_user_id,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db_session.add(record)
    await db_session.flush()
    return record


@asynccontextmanager
async def _client_as(
    db_session: AsyncSession,
    fake_redis: fakeredis.aioredis.FakeRedis,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
) -> AsyncGenerator[AsyncClient]:
    """A client whose session carries an explicit role.

    The module router is gated twice — `require_module` on the club's sports and
    a role on every endpoint — and only the second one can tell a plain member of
    a *shooting* club apart from its board. That is what this is for.
    """
    import app.redis as redis_module
    from app.database import get_db_session
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    original_redis = redis_module._redis_client
    redis_module._redis_client = fake_redis

    token = uuid.uuid4().hex
    await fake_redis.set(
        f"session:{token}",
        json.dumps({"user_id": str(user_id), "tenant_id": str(tenant_id), "role": role}),
        ex=3600,
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={"unefy_session": token},
        ) as client:
            yield client
    finally:
        redis_module._redis_client = original_redis
        app.dependency_overrides.clear()


async def _create_rule(client: AsyncClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "rule_key": "dsb-standard",
        "label": "18 Termine oder monatlich",
        "window_months": 12,
        "min_total_days": 3,
    }
    payload.update(overrides)
    response = await client.post(f"{BASE}/rules", json=payload)
    assert response.status_code == 201, response.text
    data: dict[str, object] = response.json()["data"]
    return data


# --- Module gating ---


@pytest.mark.asyncio
async def test_module_endpoints_refuse_clubs_without_the_module(
    auth_client: AsyncClient,
) -> None:
    # test_tenant has no sports at all, so no module can be active.
    response = await auth_client.get(f"{BASE}/rules")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_module_endpoints_open_up_with_the_shooting_sport(
    auth_client: AsyncClient, shooting_tenant: Tenant
) -> None:
    response = await auth_client.get(f"{BASE}/rules")
    assert response.status_code == 200
    assert response.json()["data"] == []


# --- Rules ---


@pytest.mark.asyncio
async def test_rule_lifecycle(auth_client: AsyncClient, shooting_tenant: Tenant) -> None:
    rule = await _create_rule(auth_client)
    assert rule["rule_key"] == "dsb-standard"

    duplicate = await auth_client.post(
        f"{BASE}/rules",
        json={"rule_key": "dsb-standard", "label": "nochmal", "min_total_days": 1},
    )
    assert duplicate.status_code == 409

    updated = await auth_client.patch(f"{BASE}/rules/{rule['id']}", json={"min_total_days": 18})
    assert updated.status_code == 200
    assert updated.json()["data"]["min_total_days"] == 18

    deleted = await auth_client.delete(f"{BASE}/rules/{rule['id']}")
    assert deleted.status_code == 204
    assert (await auth_client.get(f"{BASE}/rules")).json()["data"] == []


@pytest.mark.asyncio
async def test_a_rule_needs_at_least_one_criterion(
    auth_client: AsyncClient, shooting_tenant: Tenant
) -> None:
    response = await auth_client.post(f"{BASE}/rules", json={"rule_key": "empty", "label": "leer"})
    assert response.status_code == 422

    rule = await _create_rule(auth_client)
    nulled = await auth_client.patch(f"{BASE}/rules/{rule['id']}", json={"min_total_days": None})
    assert nulled.status_code == 422


# --- Record details ---


@pytest.mark.asyncio
async def test_detail_upsert_creates_then_updates_and_audits(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    shooting_tenant: Tenant,
) -> None:
    member = await _add_member(db_session, shooting_tenant.id)
    record = await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 8, 1))

    created = await auth_client.patch(
        f"{BASE}/records/{record.id}",
        json={"weapon_category": "kurzwaffe", "rounds_fired": 40},
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["weapon_category"] == "kurzwaffe"

    updated = await auth_client.patch(f"{BASE}/records/{record.id}", json={"rounds_fired": 60})
    assert updated.status_code == 200
    assert updated.json()["data"]["rounds_fired"] == 60
    assert updated.json()["data"]["weapon_category"] == "kurzwaffe"

    entries = (
        (
            await db_session.execute(
                select(TenantAuditLog).where(
                    TenantAuditLog.action == "shooting_record_detail.updated"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(entries) == 2


@pytest.mark.asyncio
async def test_details_of_a_session_are_read_in_one_request(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    """The read path the entry form needs.

    Without it the form would be blind — it could write the three fields but
    never show what is already on a row, so every edit would overwrite values
    nobody could see. One request per session, not per row: the caller is a list
    of twenty people.
    """
    first = await _add_member(db_session, shooting_tenant.id)
    second = await _add_member(db_session, shooting_tenant.id)
    a = await _add_attendance(db_session, shooting_tenant.id, first.id, date(2026, 8, 1))
    b = await _add_attendance(db_session, shooting_tenant.id, second.id, date(2026, 8, 1))
    # Same evening for both, which is what makes this one query.
    b.session_id = a.session_id
    await db_session.flush()

    await auth_client.patch(f"{BASE}/records/{a.id}", json={"rounds_fired": 40})
    await auth_client.patch(f"{BASE}/records/{b.id}", json={"weapon_category": "langwaffe"})

    response = await auth_client.get(f"{BASE}/records", params={"session_id": str(a.session_id)})

    assert response.status_code == 200, response.text
    by_record = {d["attendance_record_id"]: d for d in response.json()["data"]}
    assert by_record[str(a.id)]["rounds_fired"] == 40
    assert by_record[str(b.id)]["weapon_category"] == "langwaffe"


@pytest.mark.asyncio
async def test_details_of_another_evening_stay_out_of_it(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    # Otherwise the form would show last Tuesday's disciplines on tonight's list.
    member = await _add_member(db_session, shooting_tenant.id)
    tonight = await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 8, 1))
    earlier = await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 7, 1))
    await auth_client.patch(f"{BASE}/records/{earlier.id}", json={"rounds_fired": 10})

    response = await auth_client.get(
        f"{BASE}/records", params={"session_id": str(tonight.session_id)}
    )

    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_a_removed_record_takes_its_detail_out_of_the_list(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    """A corrected-away check-in must not keep describing an evening.

    The detail row survives on purpose — the audit trail is what answers what was
    entered and taken back — but the list the form reads is about who is on it
    now.
    """
    member = await _add_member(db_session, shooting_tenant.id)
    record = await _add_attendance(
        db_session, shooting_tenant.id, member.id, date(2026, 8, 1), deleted=True
    )
    detail = ShootingRecordDetail(
        tenant_id=shooting_tenant.id, attendance_record_id=record.id, rounds_fired=25
    )
    db_session.add(detail)
    await db_session.flush()

    response = await auth_client.get(
        f"{BASE}/records", params={"session_id": str(record.session_id)}
    )

    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_reading_details_needs_the_board(
    db_session: AsyncSession,
    fake_redis: fakeredis.aioredis.FakeRedis,
    shooting_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    """A member of a shooting club passes the module gate — the role is the barrier.

    What is behind it is everybody's disciplines and round counts for an evening,
    which is board business.
    """
    async with _client_as(
        db_session, fake_redis, test_user.id, shooting_tenant.id, "member"
    ) as client:
        response = await client.get(f"{BASE}/records", params={"session_id": str(uuid.uuid4())})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_guest_records_carry_no_detail(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    record = await _add_attendance(
        db_session, shooting_tenant.id, None, date(2026, 8, 1), guest_name="Gast"
    )
    response = await auth_client.patch(
        f"{BASE}/records/{record.id}", json={"weapon_category": "langwaffe"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GUEST_RECORD"


@pytest.mark.asyncio
async def test_detail_rejects_unknown_weapon_category(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    member = await _add_member(db_session, shooting_tenant.id)
    record = await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 8, 1))
    response = await auth_client.patch(
        f"{BASE}/records/{record.id}", json={"weapon_category": "armbrust"}
    )
    assert response.status_code == 422


# --- Evaluation ---


@pytest.mark.asyncio
async def test_proof_counts_distinct_days_inside_the_window(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    member = await _add_member(db_session, shooting_tenant.id)
    await _create_rule(auth_client, min_total_days=3)

    as_of = date(2026, 8, 4)
    # Three countable days: two visits on one evening are one appointment,
    # a deleted record and one outside the window count for nothing.
    await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 7, 1))
    await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 7, 1))
    await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 6, 1))
    await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 5, 1))
    await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 4, 1), deleted=True)
    await _add_attendance(db_session, shooting_tenant.id, member.id, date(2025, 8, 1))

    response = await auth_client.get(
        f"{BASE}/proof/{member.id}",
        params={"rule_key": "dsb-standard", "as_of": as_of.isoformat()},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["session_count"] == 3
    assert data["months_covered"] == 3
    assert data["passed"] is True
    assert data["period_start"] == "2025-08-05"
    assert data["period_end"] == "2026-08-04"


@pytest.mark.asyncio
async def test_proof_ignores_sessions_of_other_sports(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    member = await _add_member(db_session, shooting_tenant.id)
    await _create_rule(auth_client, min_total_days=1)

    gymnastics = Sport(key=f"gym-{uuid.uuid4().hex[:6]}", name="Turnen", modules=[])
    db_session.add(gymnastics)
    await db_session.flush()
    division = Division(tenant_id=shooting_tenant.id, name="Turnen", sport_id=gymnastics.id)
    db_session.add(division)
    await db_session.flush()

    # A gymnastics evening must not become a shooting appointment.
    await _add_attendance(
        db_session, shooting_tenant.id, member.id, date(2026, 7, 1), division_id=division.id
    )

    response = await auth_client.get(
        f"{BASE}/proof/{member.id}",
        params={"rule_key": "dsb-standard", "as_of": "2026-08-04"},
    )
    assert response.json()["data"]["session_count"] == 0
    assert response.json()["data"]["passed"] is False


@pytest.mark.asyncio
async def test_proof_passes_on_the_monthly_criterion_alone(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    member = await _add_member(db_session, shooting_tenant.id)
    await _create_rule(auth_client, min_total_days=18, min_distinct_months=2)

    await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 7, 1))
    await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 6, 1))

    response = await auth_client.get(
        f"{BASE}/proof/{member.id}",
        params={"rule_key": "dsb-standard", "as_of": "2026-08-04"},
    )
    data = response.json()["data"]
    assert data["session_count"] == 2
    assert data["passed"] is True


async def test_self_entered_days_are_counted_and_reported_separately(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant, test_user: User
) -> None:
    """A day the member entered for themselves counts, and says so.

    The decision behind this: the supervisor has no other route to their own
    attendance, so refusing the entry would punish the people who run the range.
    Deducting it silently would be worse — it would make the system's arithmetic
    disagree with the record without saying why. So it counts, and the count is
    qualified.
    """
    member = await _add_member(db_session, shooting_tenant.id)
    await _create_rule(auth_client, min_total_days=2)
    await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 7, 1))
    await _add_attendance(
        db_session, shooting_tenant.id, member.id, date(2026, 6, 1), method="self"
    )

    response = await auth_client.get(
        f"{BASE}/proof/{member.id}", params={"rule_key": "dsb-standard", "as_of": "2026-08-04"}
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["session_count"] == 2
    assert data["passed"] is True
    assert data["self_certified_days"] == 1


async def test_a_day_with_somebody_elses_record_is_not_self_certified(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    """One attested record is enough to carry the evening.

    The supervisor who ticks themselves off at seven and is scanned by a colleague
    at eight has an attested day; the weaker record beside it changes nothing. Per
    *day*, not per record, because a day is what §14 counts.
    """
    member = await _add_member(db_session, shooting_tenant.id)
    await _create_rule(auth_client, min_total_days=1)
    await _add_attendance(
        db_session, shooting_tenant.id, member.id, date(2026, 7, 1), method="self"
    )
    await _add_attendance(
        db_session, shooting_tenant.id, member.id, date(2026, 7, 1), method="staff_scan"
    )

    response = await auth_client.get(
        f"{BASE}/proof/{member.id}", params={"rule_key": "dsb-standard", "as_of": "2026-08-04"}
    )

    data = response.json()["data"]
    assert data["session_count"] == 1
    assert data["self_certified_days"] == 0


async def test_a_supervisor_who_checked_others_in_is_corroborated(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant, test_user: User
) -> None:
    """The number that saves the honest case.

    Somebody who ticked other people off that evening was demonstrably at the
    range, and those records exist because *other* people were there. That is
    better evidence for the supervisor's presence than their own tick, and it
    costs no extra bookkeeping — it is already in the data.
    """
    supervisor = await _add_member(db_session, shooting_tenant.id)
    supervisor.user_id = test_user.id
    other = await _add_member(db_session, shooting_tenant.id)
    await db_session.flush()
    await _create_rule(auth_client, min_total_days=1)

    await _add_attendance(
        db_session,
        shooting_tenant.id,
        supervisor.id,
        date(2026, 7, 1),
        method="self",
        # As the real path writes it: the author of a self-entry is its subject.
        # It must not be allowed to corroborate itself.
        verified_by_user_id=test_user.id,
    )
    # The same evening, from the same phone: somebody else, ticked off by them.
    await _add_attendance(
        db_session,
        shooting_tenant.id,
        other.id,
        date(2026, 7, 1),
        verified_by_user_id=test_user.id,
    )
    # And an evening with nothing but their own word.
    await _add_attendance(
        db_session,
        shooting_tenant.id,
        supervisor.id,
        date(2026, 6, 1),
        method="self",
        verified_by_user_id=test_user.id,
    )

    response = await auth_client.get(
        f"{BASE}/proof/{supervisor.id}",
        params={"rule_key": "dsb-standard", "as_of": "2026-08-04"},
    )

    data = response.json()["data"]
    assert data["self_certified_days"] == 2
    assert data["corroborated_self_days"] == 1


async def test_checking_a_guest_in_corroborates_too(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant, test_user: User
) -> None:
    """The NULL trap, pinned.

    A guest row has `member_id IS NULL`, and `member_id != <uuid>` is NULL rather
    than true in SQL — so a supervisor whose evening consisted of checking guests
    in would have come out uncorroborated.
    """
    supervisor = await _add_member(db_session, shooting_tenant.id)
    supervisor.user_id = test_user.id
    await db_session.flush()
    await _create_rule(auth_client, min_total_days=1)

    await _add_attendance(
        db_session,
        shooting_tenant.id,
        supervisor.id,
        date(2026, 7, 1),
        method="self",
        verified_by_user_id=test_user.id,
    )
    await _add_attendance(
        db_session,
        shooting_tenant.id,
        None,
        date(2026, 7, 1),
        guest_name="Jonas Gast",
        verified_by_user_id=test_user.id,
    )

    response = await auth_client.get(
        f"{BASE}/proof/{supervisor.id}",
        params={"rule_key": "dsb-standard", "as_of": "2026-08-04"},
    )

    assert response.json()["data"]["corroborated_self_days"] == 1


# --- Certificates & verify ---


@pytest.mark.asyncio
async def test_certificate_freezes_what_was_counted(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    member = await _add_member(db_session, shooting_tenant.id)
    await _create_rule(auth_client, min_total_days=2)
    first = await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 7, 1))
    second = await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 6, 1))

    response = await auth_client.post(
        f"{BASE}/certificates",
        json={"member_id": str(member.id), "rule_key": "dsb-standard", "as_of": "2026-08-04"},
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["result"] == "passed"
    assert data["session_count"] == 2
    assert data["member_name"] == "Erika Musterfrau"
    assert len(data["verification_code"]) == 12
    # Both days were entered by somebody else, so nothing here rests on the
    # member's own word.
    assert data["self_certified_days"] == 0
    assert data["corroborated_self_days"] == 0

    # The hash is recomputable from the frozen fields — that is its whole claim.
    canonical = json.dumps(
        {
            "tenant_id": str(shooting_tenant.id),
            "member_id": str(member.id),
            "rule_key": "dsb-standard",
            "period_start": data["period_start"],
            "period_end": data["period_end"],
            "session_count": data["session_count"],
            "months_covered": data["months_covered"],
            # Part of the hashed set on purpose: a qualification that can be
            # edited away afterwards qualifies nothing.
            "self_certified_days": data["self_certified_days"],
            "corroborated_self_days": data["corroborated_self_days"],
            "result": data["result"],
            "record_ids": sorted([str(first.id), str(second.id)]),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    assert data["content_hash"] == hashlib.sha256(canonical.encode()).hexdigest()

    listed = await auth_client.get(f"{BASE}/certificates")
    assert listed.json()["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_verify_page_shows_the_minimum_and_nothing_more(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    member = await _add_member(db_session, shooting_tenant.id)
    await _create_rule(auth_client, min_total_days=1)
    await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 7, 1))

    issued = await auth_client.post(
        f"{BASE}/certificates",
        json={"member_id": str(member.id), "rule_key": "dsb-standard", "as_of": "2026-08-04"},
    )
    code = issued.json()["data"]["verification_code"]

    response = await auth_client.get(f"/verify/{code}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["valid"] is True
    assert data["club_name"] == "Test Club"
    # Abbreviated — whoever finds a lost PDF must not learn the full name.
    assert data["member_name"] == "Erika M."
    assert "member_id" not in data
    assert "record_ids" not in data

    unknown = await auth_client.get("/verify/nosuchcode123")
    assert unknown.status_code == 404


@pytest.mark.asyncio
async def test_revocation_needs_a_reason_and_reaches_the_verify_page(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    member = await _add_member(db_session, shooting_tenant.id)
    await _create_rule(auth_client, min_total_days=1)
    await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 7, 1))
    issued = await auth_client.post(
        f"{BASE}/certificates",
        json={"member_id": str(member.id), "rule_key": "dsb-standard", "as_of": "2026-08-04"},
    )
    certificate = issued.json()["data"]

    bare = await auth_client.post(
        f"{BASE}/certificates/{certificate['id']}/revoke", json={"reason": "x"}
    )
    assert bare.status_code == 422

    revoked = await auth_client.post(
        f"{BASE}/certificates/{certificate['id']}/revoke",
        json={"reason": "Falsche Regel angewandt"},
    )
    assert revoked.status_code == 200

    again = await auth_client.post(
        f"{BASE}/certificates/{certificate['id']}/revoke",
        json={"reason": "Nochmal"},
    )
    assert again.status_code == 409

    verify = await auth_client.get(f"/verify/{certificate['verification_code']}")
    assert verify.json()["data"]["valid"] is False
    assert verify.json()["data"]["revoked"] is True


@pytest.mark.asyncio
async def test_certificate_survives_record_correction(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    member = await _add_member(db_session, shooting_tenant.id)
    await _create_rule(auth_client, min_total_days=1)
    record = await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 7, 1))
    issued = await auth_client.post(
        f"{BASE}/certificates",
        json={"member_id": str(member.id), "rule_key": "dsb-standard", "as_of": "2026-08-04"},
    )
    frozen_hash = issued.json()["data"]["content_hash"]

    # The record is corrected away afterwards; the certificate must not move.
    record.deleted_at = datetime.now(UTC)
    await db_session.flush()

    listed = await auth_client.get(f"{BASE}/certificates")
    assert listed.json()["data"][0]["content_hash"] == frozen_hash


# --- Range book ---


@pytest.mark.asyncio
async def test_range_book_exports_the_window_as_csv(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    member = await _add_member(db_session, shooting_tenant.id)
    record = await _add_attendance(db_session, shooting_tenant.id, member.id, date(2026, 7, 1))
    await _add_attendance(
        db_session, shooting_tenant.id, None, date(2026, 7, 1), guest_name="Tages Gast"
    )
    await auth_client.patch(
        f"{BASE}/records/{record.id}",
        json={"weapon_category": "luftdruck", "rounds_fired": 40},
    )

    response = await auth_client.get(
        f"{BASE}/range-book", params={"from": "2026-07-01", "to": "2026-07-31"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    body = response.text.lstrip("﻿")
    lines = body.strip().splitlines()
    assert lines[0].startswith("Datum;Einheit;Ort;Name;")
    assert len(lines) == 3
    # German labels, not stored keys: the header row is German and the file is
    # read in Excel or handed to an authority, where "luftdruck" under
    # "Waffenart" reads like a leaked database value.
    assert any(
        "Erika Musterfrau" in line and "Luftdruck" in line and "40" in line for line in lines
    )
    assert "luftdruck" not in body
    assert "manual" not in body
    # Guests stand in the book — it answers who was on the range.
    assert any("Tages Gast" in line for line in lines)


@pytest.mark.asyncio
async def test_the_range_book_keeps_a_value_it_has_no_label_for(
    auth_client: AsyncClient, db_session: AsyncSession, shooting_tenant: Tenant
) -> None:
    """An unlabelled key must pass through, not vanish.

    `venue_scan` and `nfc_tap` are in the model's taxonomy and not built. The day
    one of them is, the book must still say what it was rather than showing an
    empty cell — losing information is the worse failure of the two.
    """
    member = await _add_member(db_session, shooting_tenant.id)
    await _add_attendance(
        db_session, shooting_tenant.id, member.id, date(2026, 7, 2), method="venue_scan"
    )

    response = await auth_client.get(
        f"{BASE}/range-book", params={"from": "2026-07-01", "to": "2026-07-31"}
    )

    assert "venue_scan" in response.text


# --- Roles ---


@pytest.mark.asyncio
async def test_member_role_cannot_reach_the_module(
    db_session: AsyncSession,
    fake_redis: fakeredis.aioredis.FakeRedis,
    shooting_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    async with _client_as(
        db_session, fake_redis, test_user.id, shooting_tenant.id, "member"
    ) as client:
        response = await client.get(f"{BASE}/rules")

    assert response.status_code == 403
