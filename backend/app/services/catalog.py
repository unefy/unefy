import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.catalog import ClubDiscipline, MeasurementUnit
from app.models.discipline import Discipline
from app.repositories.catalog import ClubDisciplineRepository, MeasurementUnitRepository
from app.schemas.catalog import (
    ClubDisciplineCreate,
    ClubDisciplineUpdate,
    MeasurementUnitCreate,
    MeasurementUnitUpdate,
)


class CatalogService:
    """Business logic for tenant-managed measurement units and disciplines."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.units = MeasurementUnitRepository(session, tenant_id)
        self.disciplines = ClubDisciplineRepository(session, tenant_id)

    # --- Measurement units ---

    async def create_unit(
        self, data: MeasurementUnitCreate, created_by: uuid.UUID
    ) -> MeasurementUnit:
        existing = await self.units.get_by_name(data.name)
        if existing is not None:
            raise ConflictError("A unit with this name already exists")
        unit = MeasurementUnit(
            **data.model_dump(),
            tenant_id=self.tenant_id,
            created_by=created_by,
            updated_by=created_by,
        )
        self.session.add(unit)
        await self.session.flush()
        await self.session.refresh(unit)
        return unit

    async def update_unit(
        self, unit_id: uuid.UUID, data: MeasurementUnitUpdate, updated_by: uuid.UUID
    ) -> MeasurementUnit | None:
        unit = await self.units.get_by_id(unit_id)
        if unit is None:
            return None
        fields = data.model_dump(exclude_unset=True)
        new_name = fields.get("name")
        if new_name and new_name != unit.name:
            existing = await self.units.get_by_name(new_name)
            if existing is not None:
                raise ConflictError("A unit with this name already exists")
        for field, value in fields.items():
            setattr(unit, field, value)
        unit.updated_by = updated_by
        await self.session.flush()
        await self.session.refresh(unit)
        return unit

    # --- Club disciplines ---

    async def create_discipline(
        self, data: ClubDisciplineCreate, created_by: uuid.UUID
    ) -> ClubDiscipline:
        existing = await self.disciplines.get_by_name(data.name)
        if existing is not None:
            raise ConflictError("A discipline with this name already exists")
        discipline = ClubDiscipline(
            **data.model_dump(),
            tenant_id=self.tenant_id,
            created_by=created_by,
            updated_by=created_by,
        )
        self.session.add(discipline)
        await self.session.flush()
        await self.session.refresh(discipline)
        return discipline

    async def update_discipline(
        self, discipline_id: uuid.UUID, data: ClubDisciplineUpdate, updated_by: uuid.UUID
    ) -> ClubDiscipline | None:
        discipline = await self.disciplines.get_by_id(discipline_id)
        if discipline is None:
            return None
        fields = data.model_dump(exclude_unset=True)
        new_name = fields.get("name")
        if new_name and new_name != discipline.name:
            existing = await self.disciplines.get_by_name(new_name)
            if existing is not None:
                raise ConflictError("A discipline with this name already exists")
        for field, value in fields.items():
            setattr(discipline, field, value)
        discipline.updated_by = updated_by
        await self.session.flush()
        await self.session.refresh(discipline)
        return discipline

    async def import_from_catalog(
        self, discipline_ids: list[uuid.UUID], created_by: uuid.UUID
    ) -> list[ClubDiscipline]:
        """Copy global catalog disciplines into the tenant list, skipping
        names that already exist for the tenant."""
        query = select(Discipline).where(Discipline.id.in_(discipline_ids))
        result = await self.session.execute(query)
        catalog_entries = list(result.scalars().all())

        existing_names = await self.disciplines.get_existing_names()
        created: list[ClubDiscipline] = []
        for entry in catalog_entries:
            if entry.name in existing_names:
                continue
            existing_names.add(entry.name)
            discipline = ClubDiscipline(
                tenant_id=self.tenant_id,
                name=entry.name,
                short_name=entry.short_name,
                default_unit=entry.scoring_unit,
                is_active=True,
                created_by=created_by,
                updated_by=created_by,
            )
            self.session.add(discipline)
            created.append(discipline)
        await self.session.flush()
        for discipline in created:
            await self.session.refresh(discipline)
        return created
