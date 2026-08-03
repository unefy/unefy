"""The one query in this codebase that reads soft-deleted rows.

`BaseRepository._base_query()` appends `.where(deleted_at.is_(None))`
unconditionally, and every specialised repository repeats it. That is right, and
it is left alone: a client needs to *learn about* deletions, but no screen, no
export and no report ever should, so threading an `include_deleted` flag through
nine query builders would put a footgun in every one of them where a forgotten
default leaks a deleted member into the web UI.

So sync gets its own path instead, and it is deliberately narrow — tenant filter,
keyset predicate, watermark, order, limit. No search, no joins, no computed
columns, no sort options. Being the only place tombstones are visible is a reason
to be small and auditable, not a reason to be general.

There is precedent for the carve-out: `AttendanceSessionRepository
.exists_any_state()` already steps outside the filter so the audit endpoints keep
answering after a record has been corrected away.

A side benefit of taking the model rather than a repository: `EntryRepository` is
not a `BaseRepository` subclass and is scoped to one `session_id` in its
constructor, so a flag-based refactor would have missed it entirely and could not
have served a tenant-wide entry sync at all. Here `Entry` works exactly like
`Member`.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Select, Uuid, literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import TenantModel
from app.sync.cursor import Cursor


class SyncRepository[ModelType: TenantModel]:
    """Keyset reads over one tenant's rows, tombstones included."""

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        model_class: type[ModelType],
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.model_class = model_class

    def _query(self, cursor: Cursor, watermark: datetime, limit: int) -> Select[tuple[ModelType]]:
        model = self.model_class
        updated_at = model.updated_at  # type: ignore[attr-defined]

        return (
            select(model)
            .where(model.tenant_id == self.tenant_id)
            # Row-value comparison, which Postgres supports natively and can
            # serve from a (tenant_id, updated_at, id) btree as a single forward
            # range scan — no sort node, and the scan stops at the LIMIT.
            #
            # The bound is built from typed literals rather than bare Python
            # values: `tuple_()` takes SQL expressions, and stating the types
            # keeps asyncpg from having to guess how to bind a tz-aware datetime
            # next to a UUID.
            .where(
                tuple_(updated_at, model.id)
                > tuple_(
                    literal(cursor.updated_at, DateTime(timezone=True)),
                    literal(cursor.entity_id, Uuid),
                )
            )
            .where(updated_at <= watermark)
            .order_by(updated_at, model.id)
            .limit(limit)
        )

    async def page(
        self,
        *,
        cursor: Cursor,
        watermark: datetime,
        limit: int,
    ) -> tuple[list[ModelType], bool]:
        """One page of changes, and whether another follows.

        Live rows and tombstones come back interleaved in a single ordered scan,
        and the caller partitions them. That is not an implementation detail: if
        the two were fetched as separate queries with separate limits, the
        returned cursor would be correct for one and skip rows in the other. The
        bug only surfaces once deletions and updates interleave, which is to say
        in production and not in a test anyone thought to write.

        One row over the limit is fetched to answer `has_more` without a
        `COUNT(*)`, which on an unbounded delta would be both meaningless and the
        most expensive part of the request.
        """
        result = await self.session.execute(self._query(cursor, watermark, limit + 1))
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        return rows[:limit], has_more
