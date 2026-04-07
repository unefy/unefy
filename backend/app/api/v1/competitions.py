import math
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.rate_limit import RateLimit
from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.repositories.competition import (
    CompetitionRepository,
    EntryRepository,
    ScoreboardRepository,
    SessionRepository,
)
from app.schemas.competition import (
    CompetitionCreate,
    CompetitionResponse,
    CompetitionUpdate,
    EntryCreate,
    EntryResponse,
    EntryUpdate,
    SessionCreate,
    SessionResponse,
)

router = APIRouter()


# --- Helpers ---


def _comp_repo(session: AsyncSession, auth: AuthContext) -> CompetitionRepository:
    return CompetitionRepository(session, auth.tenant_id)


def _session_repo(
    session: AsyncSession, auth: AuthContext, competition_id: uuid.UUID
) -> SessionRepository:
    return SessionRepository(session, auth.tenant_id, competition_id)


def _entry_repo(session: AsyncSession, auth: AuthContext, session_id: uuid.UUID) -> EntryRepository:
    return EntryRepository(session, auth.tenant_id, session_id)


def _comp_response(c: Any) -> dict[str, Any]:
    return CompetitionResponse.model_validate(c).model_dump(mode="json")


def _session_response(s: Any) -> dict[str, Any]:
    return SessionResponse.model_validate(s).model_dump(mode="json")


def _entry_response(e: Any) -> dict[str, Any]:
    return EntryResponse.model_validate(e).model_dump(mode="json")


def _paginated(items: list[dict[str, Any]], total: int, page: int, per_page: int) -> dict[str, Any]:
    return {
        "data": items,
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, math.ceil(total / per_page)),
        },
    }


# --- Competition CRUD ---


@router.get("")
async def list_competitions(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    competition_type: str | None = Query(default=None),
) -> dict[str, Any]:
    repo = _comp_repo(session, auth)
    offset = (page - 1) * per_page
    items = await repo.get_all(offset=offset, limit=per_page, competition_type=competition_type)
    total = await repo.count(competition_type=competition_type)
    return _paginated([_comp_response(c) for c in items], total, page, per_page)


@router.post("", dependencies=[Depends(RateLimit(limit=30, window=60, scope="comp-create"))])
async def create_competition(
    data: CompetitionCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _comp_repo(session, auth)
    comp = await repo.create(data)
    return {"data": _comp_response(comp)}


@router.get("/{competition_id}")
async def get_competition(
    competition_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _comp_repo(session, auth)
    comp = await repo.get_by_id(competition_id)
    if comp is None:
        raise NotFoundError("Competition not found")
    return {"data": _comp_response(comp)}


@router.patch("/{competition_id}")
async def update_competition(
    competition_id: uuid.UUID,
    data: CompetitionUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _comp_repo(session, auth)
    comp = await repo.update(competition_id, data)
    if comp is None:
        raise NotFoundError("Competition not found")
    return {"data": _comp_response(comp)}


@router.delete("/{competition_id}")
async def delete_competition(
    competition_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _comp_repo(session, auth)
    if not await repo.soft_delete(competition_id):
        raise NotFoundError("Competition not found")
    return {"data": {"message": "Deleted"}}


# --- Scoreboard ---


@router.get("/{competition_id}/scoreboard")
async def scoreboard(
    competition_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    discipline: str | None = Query(default=None),
) -> dict[str, Any]:
    # Verify competition exists.
    repo = _comp_repo(session, auth)
    comp = await repo.get_by_id(competition_id)
    if comp is None:
        raise NotFoundError("Competition not found")

    sb_repo = ScoreboardRepository(session, auth.tenant_id)
    rows = await sb_repo.scoreboard(competition_id, discipline=discipline)

    # Sort by scoring_mode.
    reverse = comp.scoring_mode == "highest_wins"
    rows.sort(key=lambda r: r["total_score"], reverse=reverse)

    # Add rank.
    for i, row in enumerate(rows):
        row["rank"] = i + 1

    return {"data": rows, "scoring_mode": comp.scoring_mode, "scoring_unit": comp.scoring_unit}


# --- Session CRUD (nested under /competitions/{id}/sessions) ---


@router.get("/{competition_id}/sessions")
async def list_sessions(
    competition_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    repo = _session_repo(session, auth, competition_id)
    offset = (page - 1) * per_page
    items = await repo.get_all(offset=offset, limit=per_page)
    total = await repo.count()
    return _paginated([_session_response(s) for s in items], total, page, per_page)


@router.post(
    "/{competition_id}/sessions",
    dependencies=[Depends(RateLimit(limit=30, window=60, scope="session-create"))],
)
async def create_session(
    competition_id: uuid.UUID,
    data: SessionCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    # Verify competition exists.
    comp_repo = _comp_repo(session, auth)
    if await comp_repo.get_by_id(competition_id) is None:
        raise NotFoundError("Competition not found")
    repo = _session_repo(session, auth, competition_id)
    s = await repo.create(data)
    return {"data": _session_response(s)}


@router.delete("/{competition_id}/sessions/{session_id}")
async def delete_session(
    competition_id: uuid.UUID,
    session_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _session_repo(session, auth, competition_id)
    if not await repo.soft_delete(session_id):
        raise NotFoundError("Session not found")
    return {"data": {"message": "Deleted"}}


# --- Entry CRUD (nested under /sessions/{id}/entries) ---


@router.get("/{competition_id}/sessions/{session_id}/entries")
async def list_entries(
    competition_id: uuid.UUID,
    session_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=500, ge=1, le=500),
    member_id: uuid.UUID | None = Query(default=None),  # noqa: B008
) -> dict[str, Any]:
    repo = _entry_repo(session, auth, session_id)
    offset = (page - 1) * per_page
    items = await repo.get_all(offset=offset, limit=per_page, member_id=member_id)
    total = await repo.count(member_id=member_id)
    return _paginated([_entry_response(e) for e in items], total, page, per_page)


@router.post(
    "/{competition_id}/sessions/{session_id}/entries",
    dependencies=[Depends(RateLimit(limit=60, window=60, scope="entry-create"))],
)
async def create_entry(
    competition_id: uuid.UUID,
    session_id: uuid.UUID,
    data: EntryCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Idempotent entry creation for offline sync."""
    repo = _entry_repo(session, auth, session_id)
    entry, _created = await repo.create_idempotent(data, recorded_by=auth.user_id)
    return {"data": _entry_response(entry)}


@router.patch("/{competition_id}/sessions/{session_id}/entries/{entry_id}")
async def update_entry(
    competition_id: uuid.UUID,
    session_id: uuid.UUID,
    entry_id: uuid.UUID,
    data: EntryUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _entry_repo(session, auth, session_id)
    entry = await repo.update(entry_id, data)
    if entry is None:
        raise NotFoundError("Entry not found")
    return {"data": _entry_response(entry)}


@router.delete("/{competition_id}/sessions/{session_id}/entries/{entry_id}")
async def delete_entry(
    competition_id: uuid.UUID,
    session_id: uuid.UUID,
    entry_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    repo = _entry_repo(session, auth, session_id)
    if not await repo.soft_delete(entry_id):
        raise NotFoundError("Entry not found")
    return {"data": {"message": "Deleted"}}
