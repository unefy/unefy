import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.core.seeds import member_statuses_seed
from app.core.slug import fallback_slug, slugify
from app.models.catalog import MeasurementUnit
from app.models.division import Division
from app.models.function import CatalogFunction, Function
from app.models.sport import CatalogUnit, Sport
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User

logger = structlog.get_logger()

MAX_DIVISIONS = 20


class OnboardingService:
    """Creates a club and everything it needs to be usable on day one."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def unique_slug(self, name: str) -> str:
        """Derive a readable slug from the club name, suffixing on collision."""
        base = slugify(name) or fallback_slug()

        taken = set(
            (await self.session.execute(select(Tenant.slug).where(Tenant.slug.like(f"{base}%"))))
            .scalars()
            .all()
        )
        if base not in taken:
            return base

        for suffix in range(2, 100):
            candidate = f"{base}-{suffix}"
            if candidate not in taken:
                return candidate
        return fallback_slug()

    async def resolve_sports(self, sport_keys: list[str]) -> dict[str, Sport]:
        """Look up the chosen sports, rejecting unknown or inactive ones."""
        result = await self.session.execute(
            select(Sport).where(Sport.key.in_(sport_keys)).where(Sport.is_active.is_(True))
        )
        found = {sport.key: sport for sport in result.scalars().all()}

        missing = [key for key in sport_keys if key not in found]
        if missing:
            raise ValidationError(f"Unknown or inactive sport(s): {', '.join(missing)}")
        return found

    async def create_club(
        self,
        user_id: uuid.UUID,
        club_name: str,
        divisions: list[tuple[str, str]],
        has_divisions: bool,
        function_keys: list[str] | None = None,
    ) -> Tenant:
        """Create the tenant, its divisions, seeded units and the owner link.

        `divisions` is a list of `(name, sport_key)`. A club without divisions
        passes exactly one, which becomes the invisible primary division.
        """
        if not divisions:
            raise ValidationError("At least one division is required")
        if len(divisions) > MAX_DIVISIONS:
            raise ValidationError(f"At most {MAX_DIVISIONS} divisions are allowed")
        if not has_divisions and len(divisions) > 1:
            raise ValidationError("A club without divisions must select exactly one sport")

        names = [name.strip() for name, _ in divisions]
        if any(not name for name in names):
            raise ValidationError("Division names must not be empty")
        if len(set(names)) != len(names):
            raise ValidationError("Division names must be unique")

        sports = await self.resolve_sports([key for _, key in divisions])

        owner = (
            await self.session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()

        tenant = Tenant(
            name=club_name.strip(),
            slug=await self.unique_slug(club_name),
            has_divisions=has_divisions,
            member_statuses=member_statuses_seed(owner.locale if owner else None),
        )
        self.session.add(tenant)
        await self.session.flush()

        for index, (name, sport_key) in enumerate(divisions):
            self.session.add(
                Division(
                    tenant_id=tenant.id,
                    name=name.strip(),
                    sport_id=sports[sport_key].id,
                    # The first entry is primary; a club always has exactly one.
                    is_primary=index == 0,
                    created_by=user_id,
                    updated_by=user_id,
                )
            )

        await self._seed_units(tenant.id, user_id, [s.id for s in sports.values()])
        await self._seed_functions(
            tenant.id,
            user_id,
            [s.id for s in sports.values()],
            has_divisions=has_divisions,
            function_keys=function_keys,
        )

        self.session.add(TenantMembership(user_id=user_id, tenant_id=tenant.id, role="owner"))
        await self.session.flush()

        logger.info(
            "club_created",
            tenant_id=str(tenant.id),
            slug=tenant.slug,
            sports=sorted(sports),
        )
        return tenant

    async def _seed_units(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, sport_ids: list[uuid.UUID]
    ) -> None:
        """Copy the catalog units of the chosen sports into the club.

        Units are copied, not referenced: the club owns its list from here on
        and later catalog edits must not rewrite an existing club's setup.
        Names are deduplicated because two sports can share a unit.
        """
        result = await self.session.execute(
            select(CatalogUnit)
            .where(CatalogUnit.sport_id.in_(sport_ids))
            .where(CatalogUnit.is_active.is_(True))
            .order_by(CatalogUnit.sort_order, CatalogUnit.name)
        )

        seen: set[str] = set()
        for unit in result.scalars().all():
            key = unit.name.casefold()
            if key in seen:
                continue
            seen.add(key)
            self.session.add(
                MeasurementUnit(
                    tenant_id=tenant_id,
                    name=unit.name,
                    symbol=unit.symbol,
                    is_active=True,
                    created_by=user_id,
                    updated_by=user_id,
                )
            )

    async def _seed_functions(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        sport_ids: list[uuid.UUID],
        *,
        has_divisions: bool,
        function_keys: list[str] | None = None,
    ) -> None:
        """Copy the catalog offices matching the club into its own list.

        Copied, not referenced — same reasoning as `_seed_units`. General
        offices (no sport) plus those of the chosen sports; `division`-level
        offices only for clubs that actually have divisions. An explicit
        `function_keys` subset (onboarding wizard) narrows the copy; unknown
        keys are ignored rather than rejected, since the catalog can change
        between rendering the wizard and submitting it.
        """
        query = (
            select(CatalogFunction)
            .where((CatalogFunction.sport_id.is_(None)) | (CatalogFunction.sport_id.in_(sport_ids)))
            .where(CatalogFunction.is_active.is_(True))
            .order_by(CatalogFunction.sort_order, CatalogFunction.name)
        )
        result = await self.session.execute(query)

        wanted = set(function_keys) if function_keys is not None else None
        seen: set[str] = set()
        for entry in result.scalars().all():
            if wanted is not None and entry.key not in wanted:
                continue
            if entry.level == "division" and not has_divisions:
                continue
            name_key = entry.name.casefold()
            if name_key in seen:
                continue
            seen.add(name_key)
            self.session.add(
                Function(
                    tenant_id=tenant_id,
                    name=entry.name,
                    level=entry.level,
                    suggested_role=entry.suggested_role,
                    sort_order=entry.sort_order,
                    is_active=True,
                    created_by=user_id,
                    updated_by=user_id,
                )
            )

    async def active_membership_count(self, user_id: uuid.UUID) -> int:
        return (
            await self.session.execute(
                select(func.count(TenantMembership.id))
                .where(TenantMembership.user_id == user_id)
                .where(TenantMembership.is_active.is_(True))
            )
        ).scalar_one()
