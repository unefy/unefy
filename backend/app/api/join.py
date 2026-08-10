"""The public join form — unauthenticated, per club, off unless switched on.

Lives outside `/api/v1` like `/verify`: it is not an API for our own clients
but the back end of a page a stranger fills in. That makes it the one place
where somebody with no account writes to a club's database, which is why it is
opt-in per club, rate-limited, and tells the caller nothing it does not have
to.

In particular it never reveals whether somebody is already a member. An
endpoint that answered that would be a membership lookup with extra steps.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import RateLimit
from app.database import get_db_session
from app.models.division import Division
from app.models.due import FeeType
from app.schemas.application import (
    ApplicationSubmit,
    JoinFormResponse,
    PublicDivision,
    PublicFeeType,
)
from app.services.application import ApplicationService, tenant_by_slug

router = APIRouter(tags=["join"])


@router.get(
    "/join/{slug}",
    # A form being loaded, possibly by several people from one household or
    # one club network. Generous, but not an invitation to scrape.
    dependencies=[Depends(RateLimit(limit=30, window=60, scope="join-form"))],
)
async def join_form(
    slug: str,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """What the join page needs to render: club name, fees, divisions."""
    tenant = await tenant_by_slug(session, slug)

    fee_types = (
        (
            await session.execute(
                select(FeeType)
                .where(FeeType.tenant_id == tenant.id)
                .where(FeeType.is_active.is_(True))
                .where(FeeType.deleted_at.is_(None))
                .order_by(FeeType.amount)
            )
        )
        .scalars()
        .all()
    )

    # Only offered when the club actually organises itself in divisions —
    # otherwise the single primary division is an implementation detail and
    # asking about it would confuse the applicant.
    divisions = (
        (
            await session.execute(
                select(Division).where(Division.tenant_id == tenant.id).order_by(Division.name)
            )
        )
        .scalars()
        .all()
        if tenant.has_divisions
        else []
    )

    return {
        "data": JoinFormResponse(
            club_name=tenant.name,
            fee_types=[
                PublicFeeType(id=f.id, name=f.name, amount=str(f.amount), interval=f.interval)
                for f in fee_types
            ],
            divisions=[PublicDivision(id=d.id, name=d.name) for d in divisions],
            has_divisions=tenant.has_divisions,
        ).model_dump(mode="json")
    }


@router.post(
    "/join/{slug}",
    status_code=201,
    # Tighter than the form itself: filling one in takes minutes, and nobody
    # legitimately submits five applications to one club in five minutes.
    dependencies=[Depends(RateLimit(limit=5, window=300, scope="join-submit"))],
)
async def submit_application(
    slug: str,
    data: ApplicationSubmit,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Record an application.

    The response is deliberately almost empty. It confirms receipt and says
    nothing else — not the application id, not whether this address is already
    known to the club. There is nothing here for the sender to look up later,
    on purpose: the next step is the board's, and it reaches the applicant
    through a human.
    """
    tenant = await tenant_by_slug(session, slug)
    await ApplicationService(session, tenant.id).submit(data)
    return {"data": {"received": True}}
