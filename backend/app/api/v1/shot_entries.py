"""Recording shots on a target.

Separate from `/competitions/{id}/sessions/{id}/entries` because the two answer
different questions. That route needs a session to already exist and is
board-only. This one takes a member, a day and a set of positions, works out the
context itself, and lets a member record their own series — which is the whole
point on a range with no signal and no board member in sight.
"""

import math
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.rate_limit import RateLimit
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user
from app.models.competition import Entry
from app.repositories.member import MemberRepository
from app.schemas.competition import EntryResponse, ShotEntryCreate, ShotEntryUpdate
from app.services.shot_entry import ShotEntryService

router = APIRouter()

BOARD_ROLES = ("owner", "admin", "board")


async def _own_member_id(session: AsyncSession, auth: AuthContext) -> uuid.UUID | None:
    member = await MemberRepository(session, auth.tenant).get_by_user_id(auth.user_id)
    return member.id if member else None


@router.post(
    "",
    status_code=201,
    dependencies=[Depends(RateLimit(limit=120, window=60, scope="shot-entry"))],
)
async def record_shot_entry(
    data: ShotEntryCreate,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Record one series of shots.

    Pass `session_id` to file it under an existing competition or training
    session; otherwise pass `occurred_on` and it lands in the club's automatic
    "Freies Training" series.

    Ring values are computed here from the positions — whatever the client sent
    is compared and logged, never stored. Sending the same `id` twice returns the
    existing entry, so an offline queue can retry freely.

    A plain member may only record for themselves; board and above for anyone.
    """
    if auth.role not in BOARD_ROLES:
        own = await _own_member_id(session, auth)
        if own is None:
            raise ForbiddenError("No member record is linked to this account")
        if data.member_id != own:
            raise ForbiddenError("Members may only record their own results")

    service = ShotEntryService(session, auth.tenant)
    entry, created = await service.record(data, recorded_by=auth.user_id)
    return {
        "data": EntryResponse.model_validate(entry).model_dump(mode="json"),
        "meta": {"created": created},
    }


@router.patch(
    "/{entry_id}",
    dependencies=[Depends(RateLimit(limit=120, window=60, scope="shot-entry"))],
)
async def correct_shot_entry(
    entry_id: uuid.UUID,
    data: ShotEntryUpdate,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Correct a series that was already recorded.

    Shots are rescored here, exactly as on the way in, so a corrected series is
    scored by the same rules as a fresh one. The correction is recorded in the
    entry itself — when, by whom, and what the total was before — because a
    result that changed after the fact is a different thing from one that never
    did, and on a competition sheet that difference matters.

    The same rule as recording: a plain member may only touch their own series,
    board and above anybody's.
    """
    entry = await session.get(Entry, entry_id)
    if entry is None or entry.tenant_id != auth.tenant or entry.deleted_at is not None:
        raise NotFoundError("Entry not found")

    if auth.role not in BOARD_ROLES:
        own = await _own_member_id(session, auth)
        if own is None or entry.member_id != own:
            raise ForbiddenError("Members may only correct their own results")

    service = ShotEntryService(session, auth.tenant)
    corrected = await service.update(entry_id, data, updated_by=auth.user_id)
    return {"data": EntryResponse.model_validate(corrected).model_dump(mode="json")}


@router.delete(
    "/{entry_id}",
    status_code=204,
    dependencies=[Depends(RateLimit(limit=120, window=60, scope="shot-entry"))],
)
async def delete_shot_entry(
    entry_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> None:
    """Withdraw a recorded series.

    Soft delete, like everything else here: a result that was entered and then
    removed is part of what happened on the range, and a competition record that
    can be silently emptied is not a record. `deleted_at` takes it out of every
    listing and out of scoring; nothing is erased.

    The same rule as recording and correcting: a plain member may only remove
    their own series, board and above anybody's.
    """
    entry = await session.get(Entry, entry_id)
    if entry is None or entry.tenant_id != auth.tenant or entry.deleted_at is not None:
        raise NotFoundError("Entry not found")

    if auth.role not in BOARD_ROLES:
        own = await _own_member_id(session, auth)
        if own is None or entry.member_id != own:
            raise ForbiddenError("Members may only delete their own results")

    entry.deleted_at = datetime.now(UTC)
    entry.updated_by = auth.user_id
    await session.commit()


@router.get("/me")
async def list_my_entries(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    """What the caller shot, plus what the caller entered, newest first.

    Self-service, like `/dues/me`: nothing is addressable by parameter, so this
    cannot be pointed at somebody else. A member sees their own history offline
    without the device mirroring every other member's scores.

    The second half — series this caller recorded for another shooter — is not a
    widening of who may see what. It is the caller's own data entry, made while
    standing at the target. Without it a board member who records for the person
    on the next bench watches the series vanish the moment it reaches the
    server: this endpoint rebuilds the app's entire history list, so a row it
    omits is a row the device forgets. Nine of twelve real series were invisible
    that way.

    A linked member record is therefore no longer required. A board member who
    has none of their own still has results they entered, and answering 404 hid
    every one of them.
    """
    member = await MemberRepository(session, auth.tenant).get_by_user_id(auth.user_id)

    owned = Entry.member_id == member.id if member is not None else false()
    scoped = (
        (Entry.tenant_id == auth.tenant),
        or_(owned, Entry.recorded_by == auth.user_id),
        (Entry.deleted_at.is_(None)),
    )

    total = int(await session.scalar(select(func.count()).select_from(Entry).where(*scoped)) or 0)
    rows = (
        (
            await session.execute(
                select(Entry)
                .where(*scoped)
                .order_by(Entry.recorded_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        )
        .scalars()
        .all()
    )

    return {
        "data": [EntryResponse.model_validate(e).model_dump(mode="json") for e in rows],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, math.ceil(total / per_page)),
        },
    }
