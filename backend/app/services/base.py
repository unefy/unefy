import uuid

from pydantic import BaseModel as PydanticModel

from app.models.base import BaseModel
from app.repositories.base import BaseRepository


class BaseService[
    RepoType: BaseRepository,  # type: ignore[type-arg]
    ModelType: BaseModel,
    CreateSchemaType: PydanticModel,
    UpdateSchemaType: PydanticModel,
]:
    """Generic service with standard CRUD operations.

    Subclasses add business logic, validation, and side effects.
    """

    def __init__(self, repository: RepoType) -> None:
        self.repository = repository

    async def get(self, entity_id: uuid.UUID) -> ModelType | None:
        return await self.repository.get_by_id(entity_id)

    async def list(self, *, offset: int = 0, limit: int = 20) -> list[ModelType]:
        return await self.repository.get_all(offset=offset, limit=limit)

    async def count(self) -> int:
        return await self.repository.count()

    async def create(self, data: CreateSchemaType) -> ModelType:
        return await self.repository.create(data)

    async def update(self, entity_id: uuid.UUID, data: UpdateSchemaType) -> ModelType | None:
        return await self.repository.update(entity_id, data)

    async def delete(self, entity_id: uuid.UUID) -> bool:
        return await self.repository.soft_delete(entity_id)
