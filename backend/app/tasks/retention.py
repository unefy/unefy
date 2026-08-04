"""Deletion on schedule — the two clocks of the attendance module.

Attendance data lives on two speeds (see docs/plans/attendance-and-shooting-
proof.md, "Aufbewahrung"): the evidence layer (`attendance_records`) is kept
for years and may be hard-deleted *only* here, while the technical context of
a scan (`attendance_checkin_contexts`) is a behavioural trail that must go
after weeks. Both are data-protection obligations, which is why this runs on
its own and not behind an admin button — deletion that waits for somebody to
remember it is a policy, not a practice.

## Why an in-process loop

The backend has no job runner (ARQ is reserved for genuinely heavy work), and
deletion is one cheap statement per table per day. A loop in the lifespan —
the same shape as the push fan-out — needs no extra process to deploy, which
matters for `docker compose up` self-hosting. Several Uvicorn workers each run
the loop; a Redis `SET NX` lets one of them take a sweep and the rest skip it.
The deletes are idempotent, so the lock is an economy, not a correctness
requirement — if Redis is down, sweeping twice is fine, and the sweep runs
anyway: deletion is the legally required side, so it must not wait for the
optional lock.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.attendance import AttendanceCheckinContext, AttendanceRecord
from app.models.tenant import Tenant

logger = structlog.get_logger()

#: One sweep per interval across all workers. Daily would satisfy the policy;
#: hourly keeps the interval irrelevant to tests of "expired means gone soon"
#: and costs one indexed SELECT when there is nothing to do.
SWEEP_INTERVAL_SECONDS = 3600

#: Slightly shorter than the interval so a crashed holder's lock is free again
#: by the time the next sweep is due, rather than one interval later.
LOCK_TTL_SECONDS = SWEEP_INTERVAL_SECONDS - 60

_LOCK_KEY = "retention:sweep"

#: Rows per DELETE. Retention normally removes one day's growth, but the first
#: sweep of a long-lived install (or one whose tenant just shortened the
#: period) can face years of rows, and one giant DELETE would hold locks the
#: request path then queues behind.
BATCH_SIZE = 1000


@dataclass
class RetentionStats:
    contexts_deleted: int = 0
    records_deleted: int = 0


async def run_retention_loop(
    redis: Redis,
    session_factory: Any = async_session_factory,
    interval_seconds: float = SWEEP_INTERVAL_SECONDS,
) -> None:
    """Runs until cancelled. Injectable factory for the same reason the push
    fan-out has one: the task opens its own sessions, and a test needs to hand
    it the transaction it can observe.
    """
    while True:
        try:
            if await _acquire(redis):
                async with session_factory() as session:
                    stats = await run_retention_once(session)
                if stats.contexts_deleted or stats.records_deleted:
                    logger.info(
                        "retention_swept",
                        contexts=stats.contexts_deleted,
                        records=stats.records_deleted,
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            # Next interval retries; deletion a sweep late is still deletion.
            logger.warning("retention_sweep_failed", exc_info=True)
        await asyncio.sleep(interval_seconds)


async def _acquire(redis: Redis) -> bool:
    """True when this worker should sweep. Redis being down means sweeping
    without coordination — see the module docstring for why that is the right
    side to fail on.
    """
    try:
        return bool(await redis.set(_LOCK_KEY, "1", nx=True, ex=LOCK_TTL_SECONDS))
    except Exception:
        logger.warning("retention_lock_unavailable", exc_info=True)
        return True


async def run_retention_once(session: AsyncSession) -> RetentionStats:
    """One sweep over both clocks. Commits."""
    stats = RetentionStats()
    stats.contexts_deleted = await _sweep_contexts(session)
    stats.records_deleted = await _sweep_records(session)
    await session.commit()
    return stats


async def _sweep_contexts(session: AsyncSession) -> int:
    """Hard-delete expired context rows.

    Deliberately across all tenants in one statement: `expires_at` was already
    computed from each tenant's `attendance_context_retention_days` when the
    row was written, so the per-tenant policy is baked into the predicate.
    """
    deleted = 0
    while True:
        batch = (
            select(AttendanceCheckinContext.id)
            .where(AttendanceCheckinContext.expires_at <= datetime.now(UTC))
            .limit(BATCH_SIZE)
        )
        result = await session.execute(
            delete(AttendanceCheckinContext).where(AttendanceCheckinContext.id.in_(batch))
        )
        # CursorResult carries rowcount; the base Result type does not.
        count = int(result.rowcount or 0)  # type: ignore[attr-defined]
        deleted += count
        if count < BATCH_SIZE:
            return deleted


async def _sweep_records(session: AsyncSession) -> int:
    """Hard-delete attendance records past their tenant's retention period.

    The only hard delete of `attendance_records` in the codebase — everything
    else soft-deletes with an audit entry. Soft-deleted rows age out here too:
    a corrected record is still personal data.

    Per tenant, because the period is per tenant and the cutoff day depends on
    the tenant's time zone — `occurred_on` was derived from local session time,
    so the boundary must be drawn in the same clock. Contexts riding on deleted
    records go with them via ON DELETE CASCADE; nothing else references the
    rows — a shooting-proof certificate keeps its own `record_ids` snapshot
    and `content_hash` precisely so it survives this deletion.
    """
    tenants = (
        await session.execute(select(Tenant.id, Tenant.attendance_retention_years, Tenant.timezone))
    ).all()

    deleted = 0
    for tenant_id, years, tz_name in tenants:
        deleted += await _sweep_tenant_records(session, tenant_id, years, tz_name)
    return deleted


async def _sweep_tenant_records(
    session: AsyncSession, tenant_id: uuid.UUID, years: int, tz_name: str
) -> int:
    try:
        today = datetime.now(ZoneInfo(tz_name)).date()
    except (KeyError, ValueError):
        today = datetime.now(UTC).date()
    # Calendar years, not 365-day years: "kept for 10 years" is read by humans
    # against a calendar. `timedelta` has no years, so replace() with the
    # leap-day edge folded to March 1st — a day of extra retention, never less.
    try:
        cutoff = today.replace(year=today.year - years)
    except ValueError:
        cutoff = today.replace(year=today.year - years, month=3, day=1)

    deleted = 0
    while True:
        batch = (
            select(AttendanceRecord.id)
            .where(
                AttendanceRecord.tenant_id == tenant_id,
                AttendanceRecord.occurred_on < cutoff,
            )
            .limit(BATCH_SIZE)
        )
        result = await session.execute(
            delete(AttendanceRecord).where(AttendanceRecord.id.in_(batch))
        )
        count = int(result.rowcount or 0)  # type: ignore[attr-defined]  # CursorResult
        deleted += count
        if count < BATCH_SIZE:
            return deleted
