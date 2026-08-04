"""The retention sweep — the only place attendance data is hard-deleted.

Everything here drives `run_retention_once` directly against the database:
the loop around it is scheduling, the sweep is the behaviour.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.models.attendance import (
    AttendanceCheckinContext,
    AttendanceRecord,
    AttendanceSession,
)
from app.tasks.retention import _acquire, run_retention_once


def _session(tenant_id: uuid.UUID) -> AttendanceSession:
    now = datetime.now(UTC)
    return AttendanceSession(
        tenant_id=tenant_id,
        title="Training",
        opens_at=now - timedelta(hours=2),
        closes_at=now + timedelta(hours=2),
    )


def _record(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    *,
    age_days: int,
    deleted: bool = False,
) -> AttendanceRecord:
    now = datetime.now(UTC)
    return AttendanceRecord(
        tenant_id=tenant_id,
        session_id=session_id,
        guest_name=f"Guest {uuid.uuid4().hex[:8]}",
        occurred_on=(now - timedelta(days=age_days)).date(),
        checked_in_at=now - timedelta(days=age_days),
        method="manual",
        assurance="low",
        deleted_at=now if deleted else None,
    )


def _context(
    tenant_id: uuid.UUID, record_id: uuid.UUID, *, expires_in_days: int
) -> AttendanceCheckinContext:
    return AttendanceCheckinContext(
        tenant_id=tenant_id,
        attendance_record_id=record_id,
        install_id="install-1",
        expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
    )


async def _remaining(
    db_session: AsyncSession,
    model: type[AttendanceRecord] | type[AttendanceCheckinContext],
) -> set[uuid.UUID]:
    return set((await db_session.execute(select(model.id))).scalars())


@pytest.mark.asyncio
async def test_expired_context_is_deleted_and_the_digest_survives(
    db_session: AsyncSession, test_tenant: Tenant
) -> None:
    session = _session(test_tenant.id)
    db_session.add(session)
    await db_session.flush()

    kept_record = _record(test_tenant.id, session.id, age_days=1)
    gone_record = _record(test_tenant.id, session.id, age_days=1)
    gone_record.context_digest = "a" * 64
    gone_record.context_verdict = "unchecked"
    db_session.add_all([kept_record, gone_record])
    await db_session.flush()

    db_session.add_all(
        [
            _context(test_tenant.id, kept_record.id, expires_in_days=30),
            _context(test_tenant.id, gone_record.id, expires_in_days=-1),
        ]
    )
    await db_session.flush()

    stats = await run_retention_once(db_session)

    assert stats.contexts_deleted == 1
    remaining = await _remaining(db_session, AttendanceCheckinContext)
    assert len(remaining) == 1

    # The record itself stays, and with it the lasting fingerprint — that is
    # the whole point of the two-layer design.
    survivor = await db_session.get(AttendanceRecord, gone_record.id)
    assert survivor is not None
    assert survivor.context_digest == "a" * 64


@pytest.mark.asyncio
async def test_records_past_the_tenant_retention_are_deleted(
    db_session: AsyncSession, test_tenant: Tenant
) -> None:
    test_tenant.attendance_retention_years = 10
    session = _session(test_tenant.id)
    db_session.add(session)
    await db_session.flush()

    old = _record(test_tenant.id, session.id, age_days=11 * 365)
    recent = _record(test_tenant.id, session.id, age_days=9 * 365)
    db_session.add_all([old, recent])
    await db_session.flush()

    # A context still riding on the expired record goes with it (CASCADE),
    # even though its own clock has not run out.
    db_session.add(_context(test_tenant.id, old.id, expires_in_days=30))
    await db_session.flush()

    stats = await run_retention_once(db_session)

    assert stats.records_deleted == 1
    assert await _remaining(db_session, AttendanceRecord) == {recent.id}
    assert await _remaining(db_session, AttendanceCheckinContext) == set()


@pytest.mark.asyncio
async def test_soft_deleted_records_age_out_too(
    db_session: AsyncSession, test_tenant: Tenant
) -> None:
    session = _session(test_tenant.id)
    db_session.add(session)
    await db_session.flush()

    corrected = _record(test_tenant.id, session.id, age_days=11 * 365, deleted=True)
    db_session.add(corrected)
    await db_session.flush()

    stats = await run_retention_once(db_session)

    assert stats.records_deleted == 1
    assert await _remaining(db_session, AttendanceRecord) == set()


@pytest.mark.asyncio
async def test_each_tenant_is_measured_against_its_own_period(
    db_session: AsyncSession, test_tenant: Tenant
) -> None:
    test_tenant.attendance_retention_years = 10
    short_tenant = Tenant(
        id=uuid.uuid4(),
        name="Short Retention Club",
        slug="short-retention",
        attendance_retention_years=1,
    )
    db_session.add(short_tenant)
    await db_session.flush()

    session_a = _session(test_tenant.id)
    session_b = _session(short_tenant.id)
    db_session.add_all([session_a, session_b])
    await db_session.flush()

    # Same age, different verdicts: five-year-old attendance is well inside a
    # ten-year period and well past a one-year one.
    keeper = _record(test_tenant.id, session_a.id, age_days=5 * 365)
    goner = _record(short_tenant.id, session_b.id, age_days=5 * 365)
    db_session.add_all([keeper, goner])
    await db_session.flush()

    stats = await run_retention_once(db_session)

    assert stats.records_deleted == 1
    assert await _remaining(db_session, AttendanceRecord) == {keeper.id}


@pytest.mark.asyncio
async def test_nothing_to_do_deletes_nothing(db_session: AsyncSession, test_tenant: Tenant) -> None:
    session = _session(test_tenant.id)
    db_session.add(session)
    await db_session.flush()
    fresh = _record(test_tenant.id, session.id, age_days=1)
    db_session.add(fresh)
    await db_session.flush()

    stats = await run_retention_once(db_session)

    assert stats.contexts_deleted == 0
    assert stats.records_deleted == 0
    assert await _remaining(db_session, AttendanceRecord) == {fresh.id}


@pytest.mark.asyncio
async def test_the_lock_admits_one_sweeper_per_interval(fake_redis) -> None:  # type: ignore[no-untyped-def]
    assert await _acquire(fake_redis) is True
    # A second worker inside the same interval steps back.
    assert await _acquire(fake_redis) is False
