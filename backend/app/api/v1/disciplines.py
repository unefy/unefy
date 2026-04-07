"""Discipline catalog API. Global (not tenant-scoped) — read-only list
of official sport disciplines. Used by all clients to populate discipline
pickers.
"""

import math
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user
from app.models.discipline import Discipline

router = APIRouter()


@router.get("")
async def list_disciplines(
    _auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    search: str | None = Query(default=None),
    federation: str | None = Query(default=None),
    category: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    query = select(Discipline).where(Discipline.is_active.is_(True))

    if federation:
        query = query.where(Discipline.federation == federation)
    if category:
        query = query.where(Discipline.category == category)
    if search:
        like = f"%{search}%"
        query = query.where(
            Discipline.name.ilike(like)
            | Discipline.short_name.ilike(like)
            | Discipline.federation.ilike(like)
            | Discipline.category.ilike(like)
            | Discipline.caliber.ilike(like)
            | Discipline.distance.ilike(like)
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    query = query.order_by(Discipline.federation, Discipline.category, Discipline.name)
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(query)
    items = list(result.scalars().all())

    return {
        "data": [
            {
                "id": str(d.id),
                "slug": d.slug,
                "name": d.name,
                "short_name": d.short_name,
                "description": d.description,
                "federation": d.federation,
                "federation_id": d.federation_id,
                "category": d.category,
                "distance": d.distance,
                "caliber": d.caliber,
                "target_type": d.target_type,
                "scoring_unit": d.scoring_unit,
                "scoring_mode": d.scoring_mode,
                "shot_count": d.shot_count,
            }
            for d in items
        ],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, math.ceil(total / per_page)),
        },
    }


@router.get("/{slug}")
async def get_discipline(
    slug: str,
    _auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    result = await session.execute(select(Discipline).where(Discipline.slug == slug))
    d = result.scalar_one_or_none()
    if d is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Discipline not found")
    return {
        "data": {
            "id": str(d.id),
            "slug": d.slug,
            "name": d.name,
            "short_name": d.short_name,
            "description": d.description,
            "federation": d.federation,
            "federation_id": d.federation_id,
            "category": d.category,
            "distance": d.distance,
            "caliber": d.caliber,
            "target_type": d.target_type,
            "scoring_unit": d.scoring_unit,
            "scoring_mode": d.scoring_mode,
            "shot_count": d.shot_count,
        },
    }
