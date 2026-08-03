"""Regression tests for BaseRepository behaviour that delta sync depends on.

These are not tests of the sync endpoints — they cover the two repository
guarantees the sync contract is built on top of, both of which were broken and
in ways that no existing test could have noticed.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.models.member import Member
from app.repositories.member import MemberRepository
from app.schemas.competition import EntryCreate


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


async def _add_competition_session(
    session: AsyncSession, tenant_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    """A competition, one of its sessions, and a shooter to score."""
    from app.models.competition import Competition
    from app.models.competition import Session as CompetitionSession

    competition = Competition(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Vereinsmeisterschaft",
        competition_type="competition",
        start_date=date(2026, 3, 1),
        scoring_unit="Ringe",
        scoring_mode="highest_wins",
    )
    session.add(competition)
    await session.flush()

    comp_session = CompetitionSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        competition_id=competition.id,
        date=date(2026, 3, 7),
    )
    session.add(comp_session)
    await session.flush()

    shooter = await _add_member(session, tenant_id, member_number="800")
    return comp_session.id, shooter.id


def _entry_payload(entry_id: uuid.UUID, member_id: uuid.UUID) -> "EntryCreate":
    return EntryCreate(
        id=entry_id,
        member_id=member_id,
        score_value=Decimal("98.0"),
        score_unit="Ringe",
        recorded_at=datetime(2026, 3, 7, 10, 0, tzinfo=UTC),
    )


class TestSoftDeleteManyTouchesUpdatedAt:
    """A bulk soft delete must move `updated_at`, or the deletion is invisible.

    Delta sync orders by `updated_at`. A tombstone still carrying the timestamp
    the row had *before* it was deleted sorts behind every cursor already handed
    out, so no client is ever told. `POST /members/bulk-delete` would remove
    fifty members server-side and leave all fifty on every phone, forever.

    Today the guarantee comes from SQLAlchemy, not from this repository:
    `onupdate=func.now()` is applied to Core UPDATE statements as well as to ORM
    flushes, so the emitted SQL is `SET updated_at=now(), deleted_at=...`.
    Nothing in `soft_delete_many` asks for it, which is exactly why it deserves
    a test — a later switch to `text()`, or an `.execution_options()` that
    suppresses column defaults, would drop it silently and break sync rather
    than anything visible here.
    """

    async def test_bulk_soft_delete_restamps_a_long_untouched_row(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """A row last written long ago must come back stamped now.

        The row's `updated_at` is aged deliberately, and that is what gives the
        test teeth. `func.now()` in Postgres is the *transaction* timestamp, so
        inside a single test transaction an insert and a delete share one value
        and any "did it move forward" check is vacuous. Backdating first
        reproduces what production looks like: a member created months ago,
        bulk-deleted today.
        """
        member = await _add_member(db_session, test_tenant.id, member_number="001")
        stale = datetime(2020, 1, 1, tzinfo=UTC)
        await db_session.execute(
            update(Member).where(Member.id == member.id).values(updated_at=stale)
        )
        await db_session.flush()

        repo = MemberRepository(db_session, test_tenant.id)
        deleted = await repo.soft_delete_many([member.id])
        assert deleted == 1

        # expire_on_commit=False on the test session, so re-read explicitly
        # rather than trusting the identity-map copy.
        await db_session.refresh(member)
        assert member.deleted_at is not None
        assert member.updated_at is not None
        assert member.updated_at > stale, (
            "a bulk soft delete left updated_at at 2020, so the tombstone would "
            "sort before every cursor already issued and reach no client"
        )

    async def test_bulk_soft_delete_stays_tenant_scoped(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """Adding updated_at to the UPDATE must not widen what it touches."""
        own = await _add_member(db_session, test_tenant.id, member_number="003")
        other_tenant = Tenant(id=uuid.uuid4(), name="Other", slug="other-bulk")
        db_session.add(other_tenant)
        await db_session.flush()
        foreign = await _add_member(db_session, other_tenant.id, member_number="004")
        foreign_updated_at = foreign.updated_at

        repo = MemberRepository(db_session, test_tenant.id)
        assert await repo.soft_delete_many([own.id, foreign.id]) == 1

        await db_session.refresh(own)
        await db_session.refresh(foreign)
        assert own.deleted_at is not None
        assert foreign.deleted_at is None
        assert foreign.updated_at == foreign_updated_at


class TestCreateIdempotentKeepsTheTransaction:
    """A duplicate insert must cost a savepoint, not the whole request.

    `create_idempotent` used to call `session.rollback()` in its IntegrityError
    handler. That is not a savepoint rollback — it discards every uncommitted
    change the request had already made, including audit rows, to recover from
    the exact duplicate the method exists to tolerate.
    """

    async def test_earlier_writes_survive_a_pk_collision(
        self,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """A soft-deleted row is the realistic way into the IntegrityError path.

        `get_by_id` filters `deleted_at IS NULL`, but the primary key does not
        care: an entry that was created, then corrected away, then re-sent by a
        client replaying its offline queue under the same client UUID takes the
        get-then-insert check straight into a PK violation. The exception is
        correct to propagate — what must not happen is that recovering from it
        takes unrelated writes down with it.

        The plain duplicate case never reaches this code at all: `get_by_id`
        finds the live row and returns it, which is why a test built on two
        successive creates would pass no matter what the handler does.
        """
        from app.repositories.competition import EntryRepository

        comp_session_id, shooter_id = await _add_competition_session(db_session, test_tenant.id)
        repo = EntryRepository(db_session, test_tenant.id, comp_session_id)

        entry_id = uuid.uuid4()
        payload = _entry_payload(entry_id, shooter_id)
        first, created = await repo.create_idempotent(payload)
        assert created is True

        # Corrected away. Gone as far as every read path is concerned, still
        # occupying its primary key.
        assert await repo.soft_delete(first.id) is True

        # A row written before the retry. If the collision handler rolls back the
        # request transaction rather than a savepoint, this goes with it.
        bystander = await _add_member(db_session, test_tenant.id, member_number="900")

        with pytest.raises(IntegrityError):
            await repo.create_idempotent(payload)

        # The savepoint absorbed the failed insert, so the session is still
        # usable and everything written before it is still there.
        found = await MemberRepository(db_session, test_tenant.id).get_by_id(bystander.id)
        assert found is not None, (
            "recovering from the PK collision rolled back the whole request "
            "transaction and took an unrelated write with it"
        )


class TestMigrationFailureIsFatal:
    """A failed migration must stop the boot, not be logged and shrugged off."""

    async def test_run_migrations_reraises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import asyncio

        from app import main

        async def explode(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("alembic said no")

        monkeypatch.setattr(asyncio, "to_thread", explode)

        with pytest.raises(RuntimeError, match="alembic said no"):
            await main.run_migrations()
