from app.models.catalog import ClubDiscipline, MeasurementUnit
from app.repositories.base import BaseRepository
from app.schemas.catalog import (
    ClubDisciplineCreate,
    ClubDisciplineUpdate,
    MeasurementUnitCreate,
    MeasurementUnitUpdate,
)


class MeasurementUnitRepository(
    BaseRepository[MeasurementUnit, MeasurementUnitCreate, MeasurementUnitUpdate]
):
    model_class = MeasurementUnit

    async def get_by_name(self, name: str) -> MeasurementUnit | None:
        query = self._base_query().where(MeasurementUnit.name == name)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 200,
        include_inactive: bool = False,
    ) -> list[MeasurementUnit]:
        query = self._base_query()
        if not include_inactive:
            query = query.where(MeasurementUnit.is_active.is_(True))
        query = query.order_by(MeasurementUnit.name.asc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())


class ClubDisciplineRepository(
    BaseRepository[ClubDiscipline, ClubDisciplineCreate, ClubDisciplineUpdate]
):
    model_class = ClubDiscipline

    async def get_by_name(self, name: str) -> ClubDiscipline | None:
        query = self._base_query().where(ClubDiscipline.name == name)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 500,
        include_inactive: bool = False,
    ) -> list[ClubDiscipline]:
        query = self._base_query()
        if not include_inactive:
            query = query.where(ClubDiscipline.is_active.is_(True))
        query = query.order_by(ClubDiscipline.name.asc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_existing_names(self) -> set[str]:
        query = self._base_query().with_only_columns(ClubDiscipline.name)
        result = await self.session.execute(query)
        return {row[0] for row in result.all()}
