"""Delta-sync routes: `GET /api/v1/sync/{collection}`.

Separate from the existing list endpoints, not bolted onto them. `GET /members`
already carries `status`, `category`, `search`, `sort_by`, offset pagination and a
`status_counts` aggregate; supporting a second, mutually exclusive pagination mode
there would double its test matrix and put a live risk in the way — one wrong
default and tombstones leak into the web UI's member table.

Every route is twelve lines and defers to [sync_page]. They are written out
rather than generated so each one's `Depends(require_role(...))` and declared
response are visible in the source and in the OpenAPI spec.
"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user, require_role
from app.repositories.sync import SyncRepository
from app.schemas.sync import SyncMeta, Tombstone
from app.sync.cursor import (
    Cursor,
    decode_cursor,
    encode_cursor,
    start_cursor,
    watermark,
)
from app.sync.registry import COLLECTIONS, collections_for

router = APIRouter()

DEFAULT_LIMIT = 200
MAX_LIMIT = 500


async def sync_page(
    *,
    session: AsyncSession,
    auth: AuthContext,
    collection: str,
    cursor_token: str | None,
    limit: int,
) -> dict[str, Any]:
    """One page of changes for one collection.

    Tombstone inclusion follows from the cursor, not from a parameter the caller
    controls — a client-settable flag would let anyone enumerate the club's
    entire deletion history, a GDPR-relevant read dressed up as a convenience.
    A steady-state delta gets every tombstone. A bootstrap gets only the ones
    newer than the moment it began: the old ones are worthless to a client with
    no local state, but a row delivered live by an earlier page of this very
    drain can be deleted before the drain finishes, and withholding *that*
    tombstone would leave the row on the device as a live member until the
    cursor aged out a fortnight later — see [Cursor.bootstrap_started_at].

    The role gate reads the registry rather than restating it, so `/manifest`,
    the SSE fan-out and this check cannot drift apart.
    """
    spec = COLLECTIONS[collection]
    now = datetime.now(UTC)

    if cursor_token is None:
        cursor = start_cursor(bootstrap=True, started_at=watermark(now))
    else:
        cursor = decode_cursor(cursor_token, now=now)

    repo: SyncRepository[Any] = SyncRepository(session, auth.tenant, spec.model)
    rows, has_more = await repo.page(cursor=cursor, watermark=watermark(now), limit=limit)

    changed: list[dict[str, Any]] = []
    deleted: list[dict[str, Any]] = []
    for row in rows:
        if row.deleted_at is not None:
            if _tombstone_wanted(cursor, row):
                deleted.append(
                    Tombstone(id=row.id, deleted_at=row.deleted_at).model_dump(mode="json")
                )
            continue
        changed.append(spec.response.model_validate(row).model_dump(mode="json"))

    next_cursor = _advance(cursor, rows, has_more=has_more)
    meta = SyncMeta(
        cursor=encode_cursor(next_cursor),
        has_more=has_more,
        server_time=now,
        collection=collection,
    )
    return {
        "data": {"changed": changed, "deleted": deleted},
        "meta": {"sync": meta.model_dump(mode="json")},
    }


def _tombstone_wanted(cursor: Cursor, row: Any) -> bool:
    """Whether this deletion is any of the caller's business.

    Outside a bootstrap: always. Inside one: only if it happened after the
    bootstrap began, because then an earlier page of this drain may already have
    delivered the row live. Older tombstones describe rows the client never
    received, so a delete would be a no-op — and handing them out would let a
    fresh sync read the club's whole deletion history.
    """
    if not cursor.bootstrap:
        return True
    started = cursor.bootstrap_started_at
    return started is not None and row.updated_at > started


def _advance(cursor: Cursor, rows: list[Any], *, has_more: bool) -> Cursor:
    """The cursor to hand back.

    Taken from the last row of the *merged* scan, so it accounts for tombstones
    the caller filtered out — otherwise a page that was all deletions would hand
    back the cursor it was given and the client would ask for the same page
    forever.

    `bootstrap` is cleared on the last page and only there. That is what makes the
    next request start including tombstones: the client now has a local state
    worth telling about deletions from.
    """
    if not rows:
        # Nothing left to read means the bootstrap is finished, even if it read
        # nothing at all. Without clearing the flag here, a cold start against an
        # empty collection would stay in bootstrap forever and never learn about
        # a single deletion.
        return replace(cursor, bootstrap=False, bootstrap_started_at=None)
    last = rows[-1]
    still_bootstrapping = cursor.bootstrap and has_more
    return Cursor(
        updated_at=last.updated_at,
        entity_id=last.id,
        bootstrap=still_bootstrapping,
        bootstrap_started_at=cursor.bootstrap_started_at if still_bootstrapping else None,
    )


def _cursor_param() -> Any:
    return Query(default=None, max_length=512, description="Opaque; pass back what you were given")


def _limit_param() -> Any:
    return Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)


@router.get("/manifest")
async def sync_manifest(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    """What this caller may sync.

    Lets a client discover its own sync set instead of hard-coding a list that
    drifts from the server's idea of it.
    """
    return {
        "data": {
            "collections": [c.name for c in collections_for(auth.role)],
            "default_limit": DEFAULT_LIMIT,
            "max_limit": MAX_LIMIT,
        }
    }


@router.get("/members")
async def sync_members(
    auth: AuthContext = Depends(require_role(*COLLECTIONS["members"].roles)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    cursor: str | None = _cursor_param(),
    limit: int = _limit_param(),
) -> dict[str, Any]:
    return await sync_page(
        session=session, auth=auth, collection="members", cursor_token=cursor, limit=limit
    )


@router.get("/events")
async def sync_events(
    auth: AuthContext = Depends(require_role(*COLLECTIONS["events"].roles)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    cursor: str | None = _cursor_param(),
    limit: int = _limit_param(),
) -> dict[str, Any]:
    return await sync_page(
        session=session, auth=auth, collection="events", cursor_token=cursor, limit=limit
    )


@router.get("/event-registrations")
async def sync_event_registrations(
    auth: AuthContext = Depends(require_role(*COLLECTIONS["event-registrations"].roles)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    cursor: str | None = _cursor_param(),
    limit: int = _limit_param(),
) -> dict[str, Any]:
    return await sync_page(
        session=session,
        auth=auth,
        collection="event-registrations",
        cursor_token=cursor,
        limit=limit,
    )


@router.get("/dues")
async def sync_dues(
    auth: AuthContext = Depends(require_role(*COLLECTIONS["dues"].roles)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    cursor: str | None = _cursor_param(),
    limit: int = _limit_param(),
) -> dict[str, Any]:
    return await sync_page(
        session=session, auth=auth, collection="dues", cursor_token=cursor, limit=limit
    )


@router.get("/fee-types")
async def sync_fee_types(
    auth: AuthContext = Depends(require_role(*COLLECTIONS["fee-types"].roles)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    cursor: str | None = _cursor_param(),
    limit: int = _limit_param(),
) -> dict[str, Any]:
    return await sync_page(
        session=session, auth=auth, collection="fee-types", cursor_token=cursor, limit=limit
    )


@router.get("/member-fees")
async def sync_member_fees(
    auth: AuthContext = Depends(require_role(*COLLECTIONS["member-fees"].roles)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    cursor: str | None = _cursor_param(),
    limit: int = _limit_param(),
) -> dict[str, Any]:
    return await sync_page(
        session=session, auth=auth, collection="member-fees", cursor_token=cursor, limit=limit
    )


@router.get("/competitions")
async def sync_competitions(
    auth: AuthContext = Depends(require_role(*COLLECTIONS["competitions"].roles)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    cursor: str | None = _cursor_param(),
    limit: int = _limit_param(),
) -> dict[str, Any]:
    return await sync_page(
        session=session, auth=auth, collection="competitions", cursor_token=cursor, limit=limit
    )


@router.get("/competition-sessions")
async def sync_competition_sessions(
    auth: AuthContext = Depends(require_role(*COLLECTIONS["competition-sessions"].roles)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    cursor: str | None = _cursor_param(),
    limit: int = _limit_param(),
) -> dict[str, Any]:
    return await sync_page(
        session=session,
        auth=auth,
        collection="competition-sessions",
        cursor_token=cursor,
        limit=limit,
    )


@router.get("/entries")
async def sync_entries(
    auth: AuthContext = Depends(require_role(*COLLECTIONS["entries"].roles)),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    cursor: str | None = _cursor_param(),
    limit: int = _limit_param(),
) -> dict[str, Any]:
    return await sync_page(
        session=session, auth=auth, collection="entries", cursor_token=cursor, limit=limit
    )
