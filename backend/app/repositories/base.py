import uuid
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel as PydanticModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import BaseModel


class BaseRepository[
    ModelType: BaseModel,
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

    def _base_query(self) -> Any:
        query = select(self.model_class).where(self.model_class.tenant_id == self.tenant_id)
        if hasattr(self.model_class, "deleted_at"):
            query = query.where(self.model_class.deleted_at.is_(None))
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
        if hasattr(self.model_class, "deleted_at"):
            query = query.where(self.model_class.deleted_at.is_(None))
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
        if hasattr(entity, "deleted_at"):
            from datetime import UTC, datetime

            entity.deleted_at = datetime.now(UTC)
            await self.session.flush()
            return True
        return False

    async def soft_delete_many(self, entity_ids: Sequence[uuid.UUID]) -> int:
        """Soft-delete multiple entities in a single UPDATE.

        Returns the number of rows actually affected (tenant-scoped).
        """
        if not entity_ids:
            return 0
        if not hasattr(self.model_class, "deleted_at"):
            return 0

        from datetime import UTC, datetime

        from sqlalchemy import update

        stmt = (
            update(self.model_class)
            .where(self.model_class.tenant_id == self.tenant_id)
            .where(self.model_class.id.in_(entity_ids))
            .where(self.model_class.deleted_at.is_(None))
            .values(deleted_at=datetime.now(UTC))
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0
