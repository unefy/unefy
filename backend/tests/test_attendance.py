"""Tests for attendance: sessions, manual check-in, freezing, audit trail, tenant scope."""

import uuid
from datetime import date

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord
from app.models.audit import TenantAuditLog
from app.models.member import Member
from app.models.tenant import Tenant

OPENS_AT = "2026-07-07T17:00:00+00:00"
CLOSES_AT = "2026-07-07T21:00:00+00:00"


async def _add_member(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    member_number: str = "001",
    first_name: str = "Alice",
    user_id: uuid.UUID | None = None,
) -> Member:
    member = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_number=member_number,
        first_name=first_name,
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


async def _check_in(client: AsyncClient, session_id: str, member_id: uuid.UUID) -> dict:
    resp = await client.post(
        f"/api/v1/attendance/sessions/{session_id}/check-in",
        json={"member_id": str(member_id)},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# --- Sessions ---


async def test_create_and_list_sessions(auth_client: AsyncClient) -> None:
    created = await _create_session(auth_client)
    assert created["title"] == "Übungsabend"
    assert created["status"] == "open"
    assert created["record_count"] == 0

    resp = await auth_client.get("/api/v1/attendance/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["id"] == created["id"]


async def test_create_session_rejects_inverted_window(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/v1/attendance/sessions",
        json={"title": "Kaputt", "opens_at": CLOSES_AT, "closes_at": OPENS_AT},
    )
    assert resp.status_code == 422


async def test_create_session_with_unknown_supervisor(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/v1/attendance/sessions",
        json={
            "title": "Übungsabend",
            "opens_at": OPENS_AT,
            "closes_at": CLOSES_AT,
            "supervisor_member_id": str(uuid.uuid4()),
        },
    )
    assert resp.status_code == 404


async def test_session_carries_supervisor_name(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    supervisor = await _add_member(db_session, test_tenant.id, first_name="Bernd")
    created = await _create_session(auth_client, supervisor_member_id=str(supervisor.id))
    assert created["supervisor_name"] == "Bernd Example"

    resp = await auth_client.get("/api/v1/attendance/sessions")
    assert resp.json()["data"][0]["supervisor_name"] == "Bernd Example"


async def test_list_sessions_filtered_by_status(auth_client: AsyncClient) -> None:
    open_session = await _create_session(auth_client)
    closed_session = await _create_session(auth_client, title="Alt")
    await auth_client.post(f"/api/v1/attendance/sessions/{closed_session['id']}/close")

    resp = await auth_client.get("/api/v1/attendance/sessions", params={"status": "open"})
    ids = [row["id"] for row in resp.json()["data"]]
    assert ids == [open_session["id"]]


# --- Manual check-in ---


async def test_manual_check_in(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)

    record = await _check_in(auth_client, session_row["id"], member.id)
    assert record["method"] == "manual"
    # Assurance follows from the method — the caller never gets to claim it.
    assert record["assurance"] == "low"
    assert record["verified_by_user_id"] is not None
    # The calendar day comes from the session, not from the moment of the tick.
    assert record["occurred_on"] == "2026-07-07"


async def test_occurred_on_uses_the_club_timezone(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """A session opening after midnight local time belongs to that night.

    22:30 UTC on 6 July is already 00:30 on 7 July in Berlin. Filing it under
    the UTC date would put the evening on the wrong day — and the §14 count
    works on exactly that date.
    """
    test_tenant.timezone = "Europe/Berlin"
    await db_session.flush()

    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(
        auth_client,
        opens_at="2026-07-06T22:30:00+00:00",
        closes_at="2026-07-07T01:00:00+00:00",
    )
    record = await _check_in(auth_client, session_row["id"], member.id)
    assert record["occurred_on"] == "2026-07-07"


async def test_occurred_on_follows_a_changed_timezone(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """The same instant lands on a different day for a club further west."""
    test_tenant.timezone = "America/New_York"
    await db_session.flush()

    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(
        auth_client,
        opens_at="2026-07-06T22:30:00+00:00",
        closes_at="2026-07-07T01:00:00+00:00",
    )
    record = await _check_in(auth_client, session_row["id"], member.id)
    assert record["occurred_on"] == "2026-07-06"


async def test_unresolvable_timezone_does_not_block_check_in(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """A broken zone must not cost the club its evening — it falls back to UTC."""
    test_tenant.timezone = "Mars/Olympus_Mons"
    await db_session.flush()

    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    record = await _check_in(auth_client, session_row["id"], member.id)
    assert record["occurred_on"] == "2026-07-07"


async def test_club_rejects_unknown_timezone(auth_client: AsyncClient) -> None:
    resp = await auth_client.patch("/api/v1/club", json={"timezone": "Mars/Olympus_Mons"})
    assert resp.status_code == 422


async def test_club_accepts_known_timezone(auth_client: AsyncClient) -> None:
    resp = await auth_client.patch("/api/v1/club", json={"timezone": "Europe/Vienna"})
    assert resp.status_code == 200
    assert resp.json()["data"]["timezone"] == "Europe/Vienna"


async def test_check_in_rejects_unimplemented_method(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{session_row['id']}/check-in",
        json={"member_id": str(member.id), "method": "staff_scan"},
    )
    assert resp.status_code == 422


async def test_check_in_twice_conflicts(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    await _check_in(auth_client, session_row["id"], member.id)

    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{session_row['id']}/check-in",
        json={"member_id": str(member.id)},
    )
    assert resp.status_code == 409


async def test_check_in_unknown_member(auth_client: AsyncClient) -> None:
    session_row = await _create_session(auth_client)
    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{session_row['id']}/check-in",
        json={"member_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


async def test_check_out(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    record = await _check_in(auth_client, session_row["id"], member.id)

    resp = await auth_client.post(f"/api/v1/attendance/records/{record['id']}/check-out")
    assert resp.status_code == 200
    assert resp.json()["data"]["checked_out_at"] is not None

    again = await auth_client.post(f"/api/v1/attendance/records/{record['id']}/check-out")
    assert again.status_code == 409


async def test_session_detail_lists_records(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id, member_number="007")
    session_row = await _create_session(auth_client)
    await _check_in(auth_client, session_row["id"], member.id)

    resp = await auth_client.get(f"/api/v1/attendance/sessions/{session_row['id']}")
    body = resp.json()["data"]
    assert body["record_count"] == 1
    assert body["records"][0]["member_name"] == "Alice Example"
    assert body["records"][0]["member_number"] == "007"


# --- Audit trail (assurance level 0) ---


async def test_correction_requires_reason(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    record = await _check_in(auth_client, session_row["id"], member.id)

    resp = await auth_client.patch(
        f"/api/v1/attendance/records/{record['id']}", json={"note": "Nachtrag"}
    )
    assert resp.status_code == 422


async def test_correction_writes_audit_entry(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    record = await _check_in(auth_client, session_row["id"], member.id)

    resp = await auth_client.patch(
        f"/api/v1/attendance/records/{record['id']}",
        json={"note": "Gast, kein Mitglied", "reason": "Verwechslung mit A. Beispiel"},
    )
    assert resp.status_code == 200

    audit = await auth_client.get(f"/api/v1/attendance/records/{record['id']}/audit")
    entries = audit.json()["data"]
    assert len(entries) == 1
    assert entries[0]["action"] == "attendance_record.updated"
    assert entries[0]["reason"] == "Verwechslung mit A. Beispiel"
    assert entries[0]["changes"]["note"] == {"from": None, "to": "Gast, kein Mitglied"}
    assert entries[0]["actor_user_id"] is not None


async def test_correction_without_actual_change_writes_no_entry(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    record = await _check_in(auth_client, session_row["id"], member.id)

    resp = await auth_client.patch(
        f"/api/v1/attendance/records/{record['id']}",
        json={"note": None, "reason": "Nichts geändert"},
    )
    assert resp.status_code == 200

    audit = await auth_client.get(f"/api/v1/attendance/records/{record['id']}/audit")
    assert audit.json()["data"] == []


async def test_delete_record_needs_no_reason_while_the_session_is_open(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """A supervisor undoing a mistap seconds ago should not have to write prose.

    Demanding it produces "x" and "Fehler", which devalues the reasons on the
    entries where one matters. The audit entry's own actor and timestamp are
    what make an undo verifiable, and this endpoint cannot be reached at all
    once the session is closed.
    """
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    record = await _check_in(auth_client, session_row["id"], member.id)

    resp = await auth_client.delete(f"/api/v1/attendance/records/{record['id']}")

    assert resp.status_code == 204, resp.text


async def test_a_supplied_reason_still_has_to_say_something(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    # Optional is not the same as "anything goes": a one-character reason is
    # worse than none, because it looks like an explanation.
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    record = await _check_in(auth_client, session_row["id"], member.id)

    resp = await auth_client.delete(
        f"/api/v1/attendance/records/{record['id']}", params={"reason": "x"}
    )

    assert resp.status_code == 422


async def test_a_closed_session_still_refuses_removal(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """The freeze is what assurance level 0 rests on.

    Making the reason optional loosened the check-in period, not the freeze —
    after closing, a record cannot be removed with or without an explanation.
    """
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    record = await _check_in(auth_client, session_row["id"], member.id)
    await auth_client.post(f"/api/v1/attendance/sessions/{session_row['id']}/close")

    without = await auth_client.delete(f"/api/v1/attendance/records/{record['id']}")
    with_reason = await auth_client.delete(
        f"/api/v1/attendance/records/{record['id']}",
        params={"reason": "Doch nicht da gewesen"},
    )

    assert without.status_code == 409
    assert with_reason.status_code == 409


async def test_delete_record_is_soft_and_audited(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    record = await _check_in(auth_client, session_row["id"], member.id)

    resp = await auth_client.delete(
        f"/api/v1/attendance/records/{record['id']}",
        params={"reason": "War an dem Abend nicht da"},
    )
    assert resp.status_code == 204

    # Soft delete: the row survives, it just leaves the live view.
    row = await db_session.get(AttendanceRecord, uuid.UUID(record["id"]))
    assert row is not None
    assert row.deleted_at is not None

    detail = await auth_client.get(f"/api/v1/attendance/sessions/{session_row['id']}")
    assert detail.json()["data"]["record_count"] == 0

    audit = await auth_client.get(f"/api/v1/attendance/records/{record['id']}/audit")
    # The record is gone from the live view, so the trail has to stand alone:
    # it names who and when, not just that something was removed.
    entries = audit.json()["data"]
    assert len(entries) == 1
    assert entries[0]["action"] == "attendance_record.deleted"
    assert entries[0]["changes"]["member_id"] == str(member.id)
    assert entries[0]["reason"] == "War an dem Abend nicht da"


async def test_recheckin_after_deletion_is_possible(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """A member wrongly removed must be able to check in again.

    The unique index is partial for exactly this: the corrected row stays as
    history instead of blocking the new one.
    """
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    first = await _check_in(auth_client, session_row["id"], member.id)
    await auth_client.delete(
        f"/api/v1/attendance/records/{first['id']}", params={"reason": "Versehen"}
    )

    second = await _check_in(auth_client, session_row["id"], member.id)
    assert second["id"] != first["id"]


async def test_session_audit_covers_its_records(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    """One evening reads as one story, corrected-away records included."""
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    record = await _check_in(auth_client, session_row["id"], member.id)
    await auth_client.delete(
        f"/api/v1/attendance/records/{record['id']}", params={"reason": "Doch nicht da"}
    )
    await auth_client.post(f"/api/v1/attendance/sessions/{session_row['id']}/close")

    audit = await auth_client.get(f"/api/v1/attendance/sessions/{session_row['id']}/audit")
    actions = [entry["action"] for entry in audit.json()["data"]]
    assert actions == ["attendance_record.deleted", "attendance_session.closed"]
    # The actor is named, not just referenced by id.
    assert audit.json()["data"][0]["actor_name"] == "Test User"


async def test_session_update_is_audited(auth_client: AsyncClient) -> None:
    session_row = await _create_session(auth_client)
    resp = await auth_client.patch(
        f"/api/v1/attendance/sessions/{session_row['id']}",
        json={"location": "Stand 2", "reason": "Raum getauscht"},
    )
    assert resp.status_code == 200

    audit = await auth_client.get(f"/api/v1/attendance/sessions/{session_row['id']}/audit")
    entries = audit.json()["data"]
    assert entries[0]["action"] == "attendance_session.updated"
    assert entries[0]["changes"]["location"] == {"from": None, "to": "Stand 2"}


# --- Freezing ---


async def test_close_session_freezes_everything(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    other = await _add_member(db_session, test_tenant.id, member_number="002", first_name="Bob")
    session_row = await _create_session(auth_client)
    record = await _check_in(auth_client, session_row["id"], member.id)

    closed = await auth_client.post(f"/api/v1/attendance/sessions/{session_row['id']}/close")
    assert closed.status_code == 200
    assert closed.json()["data"]["status"] == "closed"
    assert closed.json()["data"]["closed_at"] is not None

    # No late entries…
    late = await auth_client.post(
        f"/api/v1/attendance/sessions/{session_row['id']}/check-in",
        json={"member_id": str(other.id)},
    )
    assert late.status_code == 409

    # …no corrections…
    correction = await auth_client.patch(
        f"/api/v1/attendance/records/{record['id']}",
        json={"note": "doch nicht", "reason": "Nachtrag"},
    )
    assert correction.status_code == 409

    # …no removals…
    removal = await auth_client.delete(
        f"/api/v1/attendance/records/{record['id']}", params={"reason": "Nachtrag"}
    )
    assert removal.status_code == 409

    # …and no editing the session itself.
    edit = await auth_client.patch(
        f"/api/v1/attendance/sessions/{session_row['id']}", json={"location": "Anderswo"}
    )
    assert edit.status_code == 409


async def test_close_records_the_frozen_count(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    await _check_in(auth_client, session_row["id"], member.id)
    await auth_client.post(f"/api/v1/attendance/sessions/{session_row['id']}/close")

    audit = await auth_client.get(f"/api/v1/attendance/sessions/{session_row['id']}/audit")
    entry = audit.json()["data"][0]
    assert entry["action"] == "attendance_session.closed"
    assert entry["changes"]["record_count"] == 1


async def test_close_twice_conflicts(auth_client: AsyncClient) -> None:
    session_row = await _create_session(auth_client)
    await auth_client.post(f"/api/v1/attendance/sessions/{session_row['id']}/close")
    resp = await auth_client.post(f"/api/v1/attendance/sessions/{session_row['id']}/close")
    assert resp.status_code == 409


async def test_delete_session_with_records_is_refused(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    await _check_in(auth_client, session_row["id"], member.id)

    resp = await auth_client.delete(
        f"/api/v1/attendance/sessions/{session_row['id']}", params={"reason": "Falsch angelegt"}
    )
    assert resp.status_code == 409


async def test_delete_empty_session(auth_client: AsyncClient) -> None:
    session_row = await _create_session(auth_client)
    resp = await auth_client.delete(
        f"/api/v1/attendance/sessions/{session_row['id']}", params={"reason": "Falsch angelegt"}
    )
    assert resp.status_code == 204

    gone = await auth_client.get(f"/api/v1/attendance/sessions/{session_row['id']}")
    assert gone.status_code == 404

    # The trail outlives its subject — a log that vanishes with the row it
    # describes proves nothing.
    audit = await auth_client.get(f"/api/v1/attendance/sessions/{session_row['id']}/audit")
    assert audit.status_code == 200
    assert audit.json()["data"][0]["action"] == "attendance_session.deleted"
    assert audit.json()["data"][0]["reason"] == "Falsch angelegt"


# --- Member views ---


async def test_member_sees_own_records(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant, test_user: object
) -> None:
    member = await _add_member(db_session, test_tenant.id, user_id=test_user.id)  # type: ignore[attr-defined]
    session_row = await _create_session(auth_client, location="Stand 1")
    await _check_in(auth_client, session_row["id"], member.id)

    resp = await auth_client.get("/api/v1/attendance/me/records")
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["session_title"] == "Übungsabend"
    assert body["data"][0]["session_location"] == "Stand 1"


async def test_me_records_without_linked_member(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/api/v1/attendance/me/records")
    assert resp.status_code == 404


async def test_board_sees_member_history(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    await _check_in(auth_client, session_row["id"], member.id)

    resp = await auth_client.get(f"/api/v1/members/{member.id}/attendance")
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 1

    filtered = await auth_client.get(
        f"/api/v1/members/{member.id}/attendance",
        params={"from_date": "2026-08-01"},
    )
    assert filtered.json()["meta"]["total"] == 0


async def test_member_history_unknown_member(auth_client: AsyncClient) -> None:
    resp = await auth_client.get(f"/api/v1/members/{uuid.uuid4()}/attendance")
    assert resp.status_code == 404


# --- Auth and tenant isolation ---


async def test_attendance_requires_authentication(anon_client: AsyncClient) -> None:
    resp = await anon_client.get("/api/v1/attendance/sessions")
    assert resp.status_code == 403


async def test_session_of_other_tenant_is_invisible(
    auth_client: AsyncClient, db_session: AsyncSession, test_tenant: Tenant
) -> None:
    other_tenant = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other_tenant)
    await db_session.flush()

    member = await _add_member(db_session, test_tenant.id)
    session_row = await _create_session(auth_client)
    await _check_in(auth_client, session_row["id"], member.id)

    # Everything written above belongs to test_tenant, including the audit trail.
    result = await db_session.execute(
        select(TenantAuditLog).where(TenantAuditLog.tenant_id == other_tenant.id)
    )
    assert result.scalars().all() == []

    foreign_member = await _add_member(db_session, other_tenant.id, member_number="X1")
    resp = await auth_client.post(
        f"/api/v1/attendance/sessions/{session_row['id']}/check-in",
        json={"member_id": str(foreign_member.id)},
    )
    assert resp.status_code == 404
