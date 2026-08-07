"""Recording a series of shots, with or without a competition behind it.

Two things happen here that the plain entry routes do not do:

1. **Context resolution.** A member on the range alone has no session to file
   under, so one is created for them — see `resolve_session`.
2. **Server-side scoring.** Every ring is recomputed from the positions. The
   client's own values are only compared and logged, never stored.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.competition import Competition, Entry
from app.models.competition import Session as CompetitionSession
from app.repositories.competition import EntryRepository
from app.repositories.member import MemberRepository
from app.repositories.target_type import TargetTypeRepository
from app.schemas.competition import (
    FREE_TRAINING_TYPE,
    EntryCreate,
    EntryDetails,
    ShotDetail,
    ShotEntryCreate,
    ShotEntryUpdate,
)
from app.services.scoring import ShotInput, TargetGeometry, score_series

logger = structlog.get_logger()

#: Namespace for deterministic free-training session ids. Fixed forever — change
#: it and every device starts inventing a second session for days it already
#: filed shots under.
FREE_TRAINING_NAMESPACE = uuid.UUID("6f3d9c21-8b47-5e0a-9d16-2c4b7a8e5f30")

FREE_TRAINING_NAME = "Freies Training"


def free_training_session_id(
    tenant_id: uuid.UUID, occurred_on: date, discipline: str | None
) -> uuid.UUID:
    """The session id for a given club, day and discipline.

    Derived rather than allocated so two phones that are both offline converge on
    the same session without talking to each other or to the server. The primary
    key collision on insert *is* the idempotency.
    """
    key = f"{tenant_id}:{occurred_on.isoformat()}:{discipline or ''}"
    return uuid.uuid5(FREE_TRAINING_NAMESPACE, key)


class ShotEntryService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.target_types = TargetTypeRepository(session)

    # --- Context ---

    async def _free_training_competition(self) -> Competition:
        """The club's automatic container, created on first use.

        A partial unique index guarantees at most one live row per tenant, so two
        concurrent first-ever recordings race into an IntegrityError rather than
        two containers. The loser re-reads the winner's row.
        """
        query = (
            select(Competition)
            .where(Competition.tenant_id == self.tenant_id)
            .where(Competition.competition_type == FREE_TRAINING_TYPE)
            .where(Competition.deleted_at.is_(None))
            .limit(1)
        )
        existing = (await self.session.execute(query)).scalar_one_or_none()
        if existing is not None:
            return existing

        entity = Competition(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            name=FREE_TRAINING_NAME,
            description=(
                "Automatisch angelegt für Trefferaufnahmen ohne Wettkampf. "
                "Enthält je Tag und Disziplin eine Einheit."
            ),
            competition_type=FREE_TRAINING_TYPE,
            start_date=datetime.now(UTC).date(),
            scoring_mode="highest_wins",
            scoring_unit="Ringe",
        )
        try:
            # Savepoint, not the request transaction: a rollback here would
            # discard whatever else this request has already written.
            async with self.session.begin_nested():
                self.session.add(entity)
                await self.session.flush()
        except IntegrityError:
            existing = (await self.session.execute(query)).scalar_one_or_none()
            if existing is not None:
                return existing
            raise
        return entity

    async def resolve_session(
        self,
        *,
        session_id: uuid.UUID | None,
        occurred_on: date | None,
        discipline: str | None,
    ) -> CompetitionSession:
        """Find the session this series belongs to, creating one if needed."""
        if session_id is not None:
            query = (
                select(CompetitionSession)
                .where(CompetitionSession.tenant_id == self.tenant_id)
                .where(CompetitionSession.id == session_id)
                .where(CompetitionSession.deleted_at.is_(None))
            )
            found = (await self.session.execute(query)).scalar_one_or_none()
            if found is None:
                raise NotFoundError("Session not found")
            return found

        if occurred_on is None:
            raise ValidationError("Either session_id or occurred_on is required")

        competition = await self._free_training_competition()
        derived_id = free_training_session_id(self.tenant_id, occurred_on, discipline)

        query = (
            select(CompetitionSession)
            .where(CompetitionSession.tenant_id == self.tenant_id)
            .where(CompetitionSession.id == derived_id)
        )
        existing = (await self.session.execute(query)).scalar_one_or_none()
        if existing is not None:
            # A previously deleted day gets revived rather than duplicated: the
            # id is derived, so there is no second row to create.
            if existing.deleted_at is not None:
                existing.deleted_at = None
                await self.session.flush()
            return existing

        entity = CompetitionSession(
            id=derived_id,
            tenant_id=self.tenant_id,
            competition_id=competition.id,
            name=None,
            date=occurred_on,
            discipline=discipline,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(entity)
                await self.session.flush()
        except IntegrityError:
            existing = (await self.session.execute(query)).scalar_one_or_none()
            if existing is not None:
                return existing
            raise
        return entity

    # --- Scoring ---

    async def geometry_for(self, target_type: str) -> TargetGeometry:
        row = await self.target_types.get_by_slug(target_type)
        if row is None:
            raise ValidationError(f"Unknown target type '{target_type}'")
        return TargetGeometry.from_model(row)

    # --- Recording ---

    async def record(
        self,
        data: ShotEntryCreate,
        *,
        recorded_by: uuid.UUID | None,
    ) -> tuple[Entry, bool]:
        """Score and store one series. Returns the entry and whether it is new."""
        # `entries.member_id` is a plain foreign key to `members.id` with no
        # tenant predicate, so without this check a club could file results
        # against another club's member: the row would carry this tenant's id and
        # a stranger's member id, and the two clubs' data would be entangled with
        # nothing to flag it.
        member = await MemberRepository(self.session, self.tenant_id).get_by_id(data.member_id)
        if member is None:
            raise NotFoundError("Member not found")

        geometry = await self.geometry_for(data.target_type)
        target_session = await self.resolve_session(
            session_id=data.session_id,
            occurred_on=data.occurred_on,
            discipline=data.discipline,
        )

        result = score_series(
            [ShotInput(x=s.x, y=s.y, caliber_mm=s.caliber_mm) for s in data.shots],
            geometry,
            data.caliber_mm,
        )

        self._log_client_drift(data, result.rings)

        details = EntryDetails(
            shots=[
                ShotDetail(
                    x=scored.x,
                    y=scored.y,
                    ring=scored.ring,
                    inner_ten=scored.inner_ten,
                    caliber_mm=scored.caliber_mm,
                    # Per shot where the client said so, falling back to the
                    # series. One series holds both: what the photo detector
                    # proposed and what the shooter placed or corrected.
                    source=sent.source or data.source,
                )
                for scored, sent in zip(result.shots, data.shots, strict=True)
            ],
            target_type=geometry.slug,
            caliber_mm=data.caliber_mm or geometry.default_caliber_mm,
            inner_tens=result.inner_tens,
            grouping_mm=result.grouping_mm,
        )

        repo = EntryRepository(self.session, self.tenant_id, target_session.id)
        return await repo.create_idempotent(
            EntryCreate(
                id=data.id,
                member_id=data.member_id,
                score_value=result.total,
                score_unit="Ringe",
                discipline=data.discipline,
                details=details.model_dump(mode="json"),
                source=data.source,
                recorded_at=data.recorded_at,
                notes=data.notes,
            ),
            recorded_by=recorded_by,
        )

    def _log_client_drift(self, data: ShotEntryCreate, server_rings: list[int]) -> None:
        """Warn when the client scored a shot differently than we just did.

        The server's value wins regardless. This log line is the only signal that
        the Kotlin and Python engines have diverged — a silent divergence would
        surface as members disputing results months later.
        """
        mismatches = [
            {"index": i, "client": shot.ring, "server": server_rings[i]}
            for i, shot in enumerate(data.shots)
            if shot.ring is not None and shot.ring != server_rings[i]
        ]
        if mismatches:
            logger.warning(
                "shot_scoring_drift",
                target_type=data.target_type,
                caliber_mm=data.caliber_mm,
                mismatches=mismatches,
            )

    async def update(
        self,
        entry_id: uuid.UUID,
        data: ShotEntryUpdate,
        *,
        updated_by: uuid.UUID | None,
    ) -> Entry:
        """Rescore a series that was already recorded.

        The ring values are recomputed here exactly as they are on the way in,
        so a corrected series is scored by the same rules as a fresh one.

        Every correction leaves a trace in `details.edits`: when, by whom, and
        what the total was before. A result that changed after the fact is a
        different thing from one that never did — on a competition sheet that
        distinction is the difference between a record and an assertion — and
        the cost of keeping it is three fields.
        """
        entry = await self.session.scalar(
            select(Entry)
            .where(Entry.id == entry_id)
            .where(Entry.tenant_id == self.tenant_id)
            .where(Entry.deleted_at.is_(None))
        )
        if entry is None:
            raise NotFoundError("Entry not found")

        previous = dict(entry.details or {})
        geometry = await self.geometry_for(data.target_type or previous.get("target_type") or "")
        caliber = data.caliber_mm or previous.get("caliber_mm")

        result = score_series(
            [ShotInput(x=s.x, y=s.y, caliber_mm=s.caliber_mm) for s in data.shots],
            geometry,
            caliber,
        )

        edits = list(previous.get("edits") or [])
        edits.append(
            {
                "at": datetime.now(UTC).isoformat(),
                "by": str(updated_by) if updated_by else None,
                "previous_total": float(entry.score_value or 0),
                "previous_shots": len(previous.get("shots") or []),
            }
        )

        details = EntryDetails(
            shots=[
                ShotDetail(
                    x=scored.x,
                    y=scored.y,
                    ring=scored.ring,
                    inner_ten=scored.inner_ten,
                    caliber_mm=scored.caliber_mm,
                    source=sent.source or "manual",
                )
                for scored, sent in zip(result.shots, data.shots, strict=True)
            ],
            target_type=geometry.slug,
            caliber_mm=caliber or geometry.default_caliber_mm,
            inner_tens=result.inner_tens,
            grouping_mm=result.grouping_mm,
        ).model_dump(mode="json")
        details["edits"] = edits

        entry.details = details
        entry.score_value = Decimal(str(result.total))
        entry.updated_by = updated_by
        if data.notes is not None:
            entry.notes = data.notes

        # Refreshed, not just flushed: `updated_at` is set by the database, and
        # serialising the response would otherwise try to load it lazily — which
        # in async SQLAlchemy is not a slow path but an error.
        await self.session.flush()
        await self.session.refresh(entry)
        return entry
