from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import AuthContext, get_authenticated_user
from app.models.sport import Sport

router = APIRouter()


@router.get("")
async def list_sports(
    _auth: AuthContext = Depends(get_authenticated_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Active sports, for the onboarding sport picker.

    Uses `get_authenticated_user` rather than `get_current_user`: the caller is
    mid-onboarding and has no tenant yet, so requiring one would make the list
    unreachable exactly when it is needed. Read-only and non-sensitive.
    """
    result = await session.execute(
        select(Sport).where(Sport.is_active.is_(True)).order_by(Sport.sort_order, Sport.name)
    )
    return {
        "data": [
            {
                "id": str(sport.id),
                "key": sport.key,
                "name": sport.name,
                "description": sport.description,
                "icon": sport.icon,
            }
            for sport in result.scalars().all()
        ]
    }
