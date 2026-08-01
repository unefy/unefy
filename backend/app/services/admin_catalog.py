import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.dependencies import AuthContext
from app.models.discipline import Discipline
from app.models.sport import CatalogUnit, Sport
from app.schemas.catalog_admin import (
    CatalogDisciplineCreate,
    CatalogDisciplineUpdate,
    CatalogUnitCreate,
    CatalogUnitUpdate,
    SportCreate,
    SportUpdate,
)
from app.services.audit import record_admin_action


class AdminCatalogService:
    """CRUD for the global master data behind every club's setup.

    These tables are read by all tenants but written only here, so a mistake
    is visible platform-wide. Every mutation is written to the admin audit log
    in the same transaction.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Sports ---

    async def list_sports(self, *, include_inactive: bool = False) -> list[dict[str, Any]]:
        unit_count = (
            select(func.count(CatalogUnit.id))
            .where(CatalogUnit.sport_id == Sport.id)
            .correlate(Sport)
            .scalar_subquery()
        )
        discipline_count = (
            select(func.count(Discipline.id))
            .where(Discipline.sport_id == Sport.id)
            .correlate(Sport)
            .scalar_subquery()
        )

        stmt = select(Sport, unit_count, discipline_count)
        if not include_inactive:
            stmt = stmt.where(Sport.is_active.is_(True))

        rows = await self.session.execute(stmt.order_by(Sport.sort_order, Sport.name))
        return [
            {
                **{
                    field: getattr(sport, field)
                    for field in (
                        "id",
                        "key",
                        "name",
                        "description",
                        "icon",
                        "sort_order",
                        "is_active",
                        "modules",
                    )
                },
                "unit_count": units,
                "discipline_count": disciplines,
            }
            for sport, units, disciplines in rows.all()
        ]

    async def get_sport(self, sport_id: uuid.UUID) -> Sport:
        sport = (
            await self.session.execute(select(Sport).where(Sport.id == sport_id))
        ).scalar_one_or_none()
        if sport is None:
            raise NotFoundError("Sport not found")
        return sport

    async def create_sport(self, auth: AuthContext, data: SportCreate, request: Request) -> Sport:
        existing = (
            await self.session.execute(select(Sport).where(Sport.key == data.key))
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(f"A sport with key '{data.key}' already exists")

        sport = Sport(id=uuid.uuid4(), **data.model_dump())
        self.session.add(sport)
        await self.session.flush()

        await record_admin_action(
            self.session,
            auth,
            "sport.create",
            request=request,
            target_type="sport",
            target_id=sport.id,
            payload={"key": sport.key, "name": sport.name},
        )
        return sport

    async def update_sport(
        self, auth: AuthContext, sport_id: uuid.UUID, data: SportUpdate, request: Request
    ) -> Sport:
        sport = await self.get_sport(sport_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(sport, field, value)
        await self.session.flush()

        await record_admin_action(
            self.session,
            auth,
            "sport.update",
            request=request,
            target_type="sport",
            target_id=sport.id,
            payload={"key": sport.key, "changes": sorted(changes)},
        )
        return sport

    async def delete_sport(self, auth: AuthContext, sport_id: uuid.UUID, request: Request) -> None:
        sport = await self.get_sport(sport_id)

        # Disciplines would be orphaned (FK is ON DELETE SET NULL) and clubs
        # already built on this sport. Deactivating hides it from onboarding
        # without rewriting history.
        linked = (
            await self.session.execute(
                select(func.count(Discipline.id)).where(Discipline.sport_id == sport.id)
            )
        ).scalar_one()
        if linked:
            raise ConflictError(
                f"{linked} discipline(s) still reference this sport — deactivate it instead"
            )

        await record_admin_action(
            self.session,
            auth,
            "sport.delete",
            request=request,
            target_type="sport",
            target_id=sport.id,
            payload={"key": sport.key, "name": sport.name},
        )
        await self.session.delete(sport)
        await self.session.flush()

    # --- Catalog units ---

    async def list_units(
        self, *, sport_id: uuid.UUID | None = None, include_inactive: bool = False
    ) -> list[CatalogUnit]:
        stmt = select(CatalogUnit)
        if sport_id is not None:
            stmt = stmt.where(CatalogUnit.sport_id == sport_id)
        if not include_inactive:
            stmt = stmt.where(CatalogUnit.is_active.is_(True))
        result = await self.session.execute(stmt.order_by(CatalogUnit.sort_order, CatalogUnit.name))
        return list(result.scalars().all())

    async def create_unit(
        self, auth: AuthContext, data: CatalogUnitCreate, request: Request
    ) -> CatalogUnit:
        await self.get_sport(data.sport_id)
        await self._assert_unit_name_free(data.sport_id, data.name)

        unit = CatalogUnit(id=uuid.uuid4(), **data.model_dump())
        self.session.add(unit)
        await self.session.flush()

        await record_admin_action(
            self.session,
            auth,
            "catalog_unit.create",
            request=request,
            target_type="catalog_unit",
            target_id=unit.id,
            payload={"name": unit.name, "sport_id": str(unit.sport_id)},
        )
        return unit

    async def update_unit(
        self,
        auth: AuthContext,
        unit_id: uuid.UUID,
        data: CatalogUnitUpdate,
        request: Request,
    ) -> CatalogUnit:
        unit = (
            await self.session.execute(select(CatalogUnit).where(CatalogUnit.id == unit_id))
        ).scalar_one_or_none()
        if unit is None:
            raise NotFoundError("Unit not found")

        changes = data.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"] != unit.name:
            await self._assert_unit_name_free(unit.sport_id, changes["name"])
        for field, value in changes.items():
            setattr(unit, field, value)
        await self.session.flush()

        await record_admin_action(
            self.session,
            auth,
            "catalog_unit.update",
            request=request,
            target_type="catalog_unit",
            target_id=unit.id,
            payload={"name": unit.name, "changes": sorted(changes)},
        )
        return unit

    async def delete_unit(self, auth: AuthContext, unit_id: uuid.UUID, request: Request) -> None:
        unit = (
            await self.session.execute(select(CatalogUnit).where(CatalogUnit.id == unit_id))
        ).scalar_one_or_none()
        if unit is None:
            raise NotFoundError("Unit not found")

        await record_admin_action(
            self.session,
            auth,
            "catalog_unit.delete",
            request=request,
            target_type="catalog_unit",
            target_id=unit.id,
            payload={"name": unit.name},
        )
        # Hard delete is safe: clubs hold copies, not references.
        await self.session.delete(unit)
        await self.session.flush()

    # --- Catalog disciplines ---

    async def list_disciplines(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        sport_id: uuid.UUID | None = None,
        federation: str | None = None,
        category: str | None = None,
        search: str | None = None,
        include_inactive: bool = False,
    ) -> tuple[list[Discipline], int]:
        stmt = select(Discipline)
        count_stmt = select(func.count(Discipline.id))

        def narrow(clause: Any) -> None:
            nonlocal stmt, count_stmt
            stmt = stmt.where(clause)
            count_stmt = count_stmt.where(clause)

        if sport_id is not None:
            narrow(Discipline.sport_id == sport_id)
        if federation:
            narrow(Discipline.federation == federation)
        if category:
            narrow(Discipline.category == category)
        if not include_inactive:
            narrow(Discipline.is_active.is_(True))
        if search:
            pattern = f"%{search}%"
            narrow(
                or_(
                    Discipline.name.ilike(pattern),
                    Discipline.short_name.ilike(pattern),
                    Discipline.slug.ilike(pattern),
                )
            )

        total = (await self.session.execute(count_stmt)).scalar_one()
        result = await self.session.execute(
            stmt.order_by(Discipline.federation, Discipline.category, Discipline.name)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_discipline(self, discipline_id: uuid.UUID) -> Discipline:
        discipline = (
            await self.session.execute(select(Discipline).where(Discipline.id == discipline_id))
        ).scalar_one_or_none()
        if discipline is None:
            raise NotFoundError("Discipline not found")
        return discipline

    async def create_discipline(
        self, auth: AuthContext, data: CatalogDisciplineCreate, request: Request
    ) -> Discipline:
        await self.get_sport(data.sport_id)

        existing = (
            await self.session.execute(select(Discipline).where(Discipline.slug == data.slug))
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(f"A discipline with slug '{data.slug}' already exists")

        discipline = Discipline(id=uuid.uuid4(), **data.model_dump())
        self.session.add(discipline)
        await self.session.flush()

        await record_admin_action(
            self.session,
            auth,
            "catalog_discipline.create",
            request=request,
            target_type="catalog_discipline",
            target_id=discipline.id,
            payload={"slug": discipline.slug, "name": discipline.name},
        )
        return discipline

    async def update_discipline(
        self,
        auth: AuthContext,
        discipline_id: uuid.UUID,
        data: CatalogDisciplineUpdate,
        request: Request,
    ) -> Discipline:
        discipline = await self.get_discipline(discipline_id)
        changes = data.model_dump(exclude_unset=True)

        if changes.get("sport_id") is not None:
            await self.get_sport(changes["sport_id"])
        for field, value in changes.items():
            setattr(discipline, field, value)
        await self.session.flush()

        await record_admin_action(
            self.session,
            auth,
            "catalog_discipline.update",
            request=request,
            target_type="catalog_discipline",
            target_id=discipline.id,
            payload={"slug": discipline.slug, "changes": sorted(changes)},
        )
        return discipline

    async def delete_discipline(
        self, auth: AuthContext, discipline_id: uuid.UUID, request: Request
    ) -> None:
        discipline = await self.get_discipline(discipline_id)

        await record_admin_action(
            self.session,
            auth,
            "catalog_discipline.delete",
            request=request,
            target_type="catalog_discipline",
            target_id=discipline.id,
            payload={"slug": discipline.slug, "name": discipline.name},
        )
        # Clubs hold copies in `club_disciplines`, so removing the catalog
        # entry cannot orphan a club's data.
        await self.session.delete(discipline)
        await self.session.flush()

    # --- Helpers ---

    async def _assert_unit_name_free(self, sport_id: uuid.UUID, name: str) -> None:
        clash = (
            await self.session.execute(
                select(CatalogUnit)
                .where(CatalogUnit.sport_id == sport_id)
                .where(func.lower(CatalogUnit.name) == name.lower())
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise ConflictError(f"'{name}' already exists for this sport")

    @staticmethod
    def assert_not_empty(value: str, field: str) -> None:
        if not value.strip():
            raise ValidationError(f"{field} must not be empty")
