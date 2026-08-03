import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel as PydanticModel
from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.outbox import queue_change
from app.models.base import TenantModel
from app.sync.registry import collection_for_model


class BaseRepository[
    ModelType: TenantModel,
    CreateSchemaType: PydanticModel,
    UpdateSchemaType: PydanticModel,
]:
    """Generic repository with mandatory tenant scoping.

    Every query is filtered by tenant_id — this is the critical
    multi-tenancy invariant that must never be bypassed.
    """

    model_class: type[ModelType]

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def _announce(self, entity_id: uuid.UUID, op: str) -> None:
        """Queue a change hint for after the commit.

        Only [soft_delete_many] needs this. Every other write in the codebase goes
        through the ORM and is picked up automatically by the flush listener in
        `app/events/outbox.py` — a bulk UPDATE does not, because it never builds an
        ORM object for the listener to see.
        """
        collection = collection_for_model(self.model_class)
        if collection is None:
            return
        queue_change(
            self.session,
            tenant_id=self.tenant_id,
            entity=collection,
            entity_id=entity_id,
            op=op,
        )

    def _deleted_at(self) -> Any:
        """The soft-delete column, or None for models that hard-delete.

        Looked up rather than declared: soft delete is opt-in per model, and a
        base class that required the column would force it on models that have
        no business keeping tombstones.
        """
        return getattr(self.model_class, "deleted_at", None)

    def _base_query(self) -> Select[tuple[ModelType]]:
        query = select(self.model_class).where(self.model_class.tenant_id == self.tenant_id)
        deleted_at = self._deleted_at()
        if deleted_at is not None:
            query = query.where(deleted_at.is_(None))
        return query

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelType | None:
        query = self._base_query().where(self.model_class.id == entity_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> list[ModelType]:
        query = self._base_query().offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count(self) -> int:
        query = (
            select(func.count())
            .select_from(self.model_class)
            .where(self.model_class.tenant_id == self.tenant_id)
        )
        deleted_at = self._deleted_at()
        if deleted_at is not None:
            query = query.where(deleted_at.is_(None))
        result = await self.session.execute(query)
        return result.scalar_one()

    async def create(self, data: CreateSchemaType) -> ModelType:
        entity = self.model_class(
            **data.model_dump(),
            tenant_id=self.tenant_id,
        )
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, entity_id: uuid.UUID, data: UpdateSchemaType) -> ModelType | None:
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(entity, field, value)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def soft_delete(self, entity_id: uuid.UUID) -> bool:
        entity = await self.get_by_id(entity_id)
        if entity is None:
            return False
        if self._deleted_at() is None:
            return False
        entity.deleted_at = datetime.now(UTC)  # type: ignore[attr-defined]
        await self.session.flush()
        return True

    async def soft_delete_many(self, entity_ids: Sequence[uuid.UUID]) -> int:
        """Soft-delete multiple entities in a single UPDATE.

        Returns the number of rows actually affected (tenant-scoped).

        `updated_at` is not listed in `.values()` and does not need to be:
        SQLAlchemy applies the column's `onupdate=func.now()` to Core UPDATE
        statements as well as to ORM flushes, so the emitted SQL is
        `SET updated_at=now(), deleted_at=…`. That matters more than it looks —
        delta sync orders tombstones by `updated_at`, and a bulk delete that
        left it behind would sort the tombstone before every cursor already
        issued and reach no client. `tests/test_repository_base.py` pins it.
        """
        if not entity_ids:
            return 0
        deleted_at = self._deleted_at()
        if deleted_at is None:
            return 0

        stmt = (
            update(self.model_class)
            .where(self.model_class.tenant_id == self.tenant_id)
            .where(self.model_class.id.in_(entity_ids))
            .where(deleted_at.is_(None))
            .values(deleted_at=datetime.now(UTC))
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        # Announced for every id asked for, not only the rows actually hit. The
        # UPDATE does not report *which* ids matched, and a spurious hint costs a
        # client one wasted delta sync while a missing one costs it a stale row.
        for entity_id in entity_ids:
            self._announce(entity_id, "delete")
        # CursorResult carries rowcount; the base Result type does not.
        return int(result.rowcount or 0)  # type: ignore[attr-defined]
