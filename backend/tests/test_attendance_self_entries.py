"""External self-entries: a member's own ledger of range days the club did not run."""

import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member import Member
from app.models.shooting import ShootingProofCertificate
from app.models.tenant import Tenant
from app.models.user import User

ENTRIES = "/api/v1/attendance/me/entries"


async def _own_member(db_session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> Member:
    member = Member(
        tenant_id=tenant_id,
        member_number=f"M-{uuid.uuid4().hex[:8]}",
        first_name="Erika",
        last_name="Musterfrau",
        joined_at=date(2024, 1, 1),
        status="active",
        user_id=user_id,
    )
    db_session.add(member)
    await db_session.flush()
    return member


def _club_today() -> date:
    """Today in the club's zone, which is the only "today" the service knows.

    `AttendanceService` bounds a self-entry against
    `datetime.now(UTC).astimezone(club_timezone).date()`, and the test tenant
    defaults to Europe/Berlin. `date.today()` agrees with that only when the
    machine running the tests happens to sit in the same zone — so on a UTC CI
    runner, every evening between 22:00 and midnight UTC, "tomorrow" here was
    the club's today and the bound tests failed for two hours a day.
    """
    return datetime.now(UTC).astimezone(ZoneInfo("Europe/Berlin")).date()


def _yesterday() -> str:
    return (_club_today() - timedelta(days=1)).isoformat()


async def test_create_entry_derives_its_credibility(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    await _own_member(db_session, test_tenant.id, test_user.id)

    resp = await auth_client.post(
        ENTRIES,
        json={"occurred_on": _yesterday(), "location": "SV Nachbarort, Stand 2"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    # Derived server-side — the request never named any of these.
    assert data["origin"] == "external"
    assert data["method"] == "self"
    assert data["assurance"] == "low"
    assert data["session_id"] is None
    assert data["external_location"] == "SV Nachbarort, Stand 2"
    assert data["occurred_on"] == _yesterday()


async def test_entries_appear_in_both_own_lists(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    member = await _own_member(db_session, test_tenant.id, test_user.id)

    # One club record for contrast, through the ordinary path.
    session_resp = await auth_client.post(
        "/api/v1/attendance/sessions",
        json={
            "title": "Übungsabend",
            "opens_at": "2026-08-04T17:00:00+00:00",
            "closes_at": "2026-08-04T21:00:00+00:00",
        },
    )
    session_id = session_resp.json()["data"]["id"]
    check_in = await auth_client.post(
        f"/api/v1/attendance/sessions/{session_id}/check-in",
        json={"member_id": str(member.id)},
    )
    assert check_in.status_code == 201

    created = await auth_client.post(
        ENTRIES, json={"occurred_on": _yesterday(), "location": "Fremder Stand"}
    )
    assert created.status_code == 201

    # /me/entries: the external ones only.
    entries = (await auth_client.get(ENTRIES)).json()["data"]
    assert [e["origin"] for e in entries] == ["external"]

    # /me/records: the full history, both kinds, external without a session.
    records = (await auth_client.get("/api/v1/attendance/me/records")).json()["data"]
    origins = {r["origin"] for r in records}
    assert origins == {"club", "external"}
    external = next(r for r in records if r["origin"] == "external")
    assert external["session_title"] is None


async def test_entry_dates_are_bounded(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    await _own_member(db_session, test_tenant.id, test_user.id)

    tomorrow = (_club_today() + timedelta(days=1)).isoformat()
    resp = await auth_client.post(ENTRIES, json={"occurred_on": tomorrow, "location": "X"})
    assert resp.status_code == 422

    long_ago = (_club_today() - timedelta(days=45)).isoformat()
    resp = await auth_client.post(ENTRIES, json={"occurred_on": long_ago, "location": "X"})
    assert resp.status_code == 422


async def test_one_entry_per_day(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    await _own_member(db_session, test_tenant.id, test_user.id)

    first = await auth_client.post(
        ENTRIES, json={"occurred_on": _yesterday(), "location": "Stand A"}
    )
    assert first.status_code == 201
    second = await auth_client.post(
        ENTRIES, json={"occurred_on": _yesterday(), "location": "Stand B"}
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "SELF_ENTRY_EXISTS"


async def test_delete_own_entry(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    await _own_member(db_session, test_tenant.id, test_user.id)
    created = await auth_client.post(
        ENTRIES, json={"occurred_on": _yesterday(), "location": "Stand A"}
    )
    entry_id = created.json()["data"]["id"]

    resp = await auth_client.delete(f"{ENTRIES}/{entry_id}")
    assert resp.status_code == 204
    assert (await auth_client.get(ENTRIES)).json()["data"] == []


async def test_delete_is_refused_once_certified(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """What has been certified cannot quietly lose its basis."""
    member = await _own_member(db_session, test_tenant.id, test_user.id)
    created = await auth_client.post(
        ENTRIES, json={"occurred_on": _yesterday(), "location": "Stand A"}
    )
    entry_id = created.json()["data"]["id"]

    db_session.add(
        ShootingProofCertificate(
            tenant_id=test_tenant.id,
            member_id=member.id,
            rule_key="dsb-standard",
            period_start=date(2025, 8, 5),
            period_end=date(2026, 8, 4),
            session_count=1,
            months_covered=1,
            self_certified_days=1,
            corroborated_self_days=0,
            external_days=1,
            result="failed",
            issued_at=datetime.now(UTC),
            issued_by_user_id=test_user.id,
            record_ids=[entry_id],
            content_hash="x" * 64,
            verification_code=uuid.uuid4().hex[:12],
        )
    )
    await db_session.flush()

    resp = await auth_client.delete(f"{ENTRIES}/{entry_id}")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "RECORD_CERTIFIED"


async def test_club_records_are_not_deletable_here(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """The member path reaches exactly the member's own external entries."""
    member = await _own_member(db_session, test_tenant.id, test_user.id)
    session_resp = await auth_client.post(
        "/api/v1/attendance/sessions",
        json={
            "title": "Übungsabend",
            "opens_at": "2026-08-04T17:00:00+00:00",
            "closes_at": "2026-08-04T21:00:00+00:00",
        },
    )
    session_id = session_resp.json()["data"]["id"]
    check_in = await auth_client.post(
        f"/api/v1/attendance/sessions/{session_id}/check-in",
        json={"member_id": str(member.id)},
    )
    record_id = check_in.json()["data"]["id"]

    resp = await auth_client.delete(f"{ENTRIES}/{record_id}")
    assert resp.status_code == 404


async def test_entries_require_authentication(anon_client: AsyncClient) -> None:
    resp = await anon_client.post(ENTRIES, json={"occurred_on": _yesterday(), "location": "X"})
    assert resp.status_code == 403
