import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel as PydanticModel
from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import TenantModel


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
        # CursorResult carries rowcount; the base Result type does not.
        return int(result.rowcount or 0)  # type: ignore[attr-defined]
