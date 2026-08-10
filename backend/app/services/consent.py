"""What a member allows, and the record of how that came to be.

The ledger is append-only. Nothing in here updates or deletes a row, and that
is the point: a consent record you can edit proves nothing, and proving what
was consented to — and that a withdrawal was honoured — is the only reason the
table exists.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent import CONSENT_KINDS, MemberConsent
from app.schemas.consent import ConsentEntry, ConsentOverview, ConsentRecord, ConsentState


class ConsentService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def record(
        self,
        member_id: uuid.UUID,
        data: ConsentRecord,
        *,
        source: str,
        recorded_by: uuid.UUID | None,
    ) -> MemberConsent:
        """Append one answer.

        Appends even when it repeats the current answer. A member who ticks a
        box, unticks it and ticks it again did that, and a ledger that quietly
        drops the middle step is no longer a record of what happened.
        """
        entry = MemberConsent(
            tenant_id=self.tenant_id,
            member_id=member_id,
            kind=data.kind,
            granted=data.granted,
            recorded_at=data.recorded_at or datetime.now(UTC),
            source=source,
            recorded_by_user_id=recorded_by,
            note=data.note,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def record_many(
        self,
        member_id: uuid.UUID,
        answers: dict[str, bool],
        *,
        source: str,
        recorded_at: datetime,
        recorded_by: uuid.UUID | None,
        note: str | None = None,
    ) -> None:
        """Several answers given at one moment — the join form's three boxes.

        All of them carry the same timestamp, because that is when the person
        answered. Unticked boxes are written too: somebody who was asked and
        said no is a different case from somebody who was never asked, and only
        writing the yesses would erase that difference.
        """
        for kind in CONSENT_KINDS:
            if kind not in answers:
                continue
            self.session.add(
                MemberConsent(
                    tenant_id=self.tenant_id,
                    member_id=member_id,
                    kind=kind,
                    granted=answers[kind],
                    recorded_at=recorded_at,
                    source=source,
                    recorded_by_user_id=recorded_by,
                    note=note,
                )
            )
        await self.session.flush()

    async def history(self, member_id: uuid.UUID) -> list[MemberConsent]:
        """Every answer this member gave, newest first."""
        query = (
            select(MemberConsent)
            .where(MemberConsent.tenant_id == self.tenant_id)
            .where(MemberConsent.member_id == member_id)
            .order_by(MemberConsent.recorded_at.desc(), MemberConsent.id.desc())
        )
        return list((await self.session.execute(query)).scalars().all())

    async def overview(self, member_id: uuid.UUID) -> ConsentOverview:
        """The current answers plus the trail that produced them."""
        entries = await self.history(member_id)

        # The history is already newest-first, so the first row seen for a kind
        # is the current answer. Done in Python rather than with a window
        # function: the list is short, and the two views come from one query.
        seen: dict[str, MemberConsent] = {}
        for entry in entries:
            seen.setdefault(entry.kind, entry)

        current = [
            ConsentState(
                kind=kind,
                granted=seen[kind].granted if kind in seen else None,
                since=seen[kind].recorded_at if kind in seen else None,
                source=seen[kind].source if kind in seen else None,
            )
            for kind in CONSENT_KINDS
        ]
        return ConsentOverview(
            current=current,
            history=[ConsentEntry.model_validate(e) for e in entries],
        )

    async def refused(self, kind: str) -> set[uuid.UUID]:
        """Members whose newest answer for this kind is no.

        Only refusals — members who were never asked are not in here. The
        club's internal directory does not rest on consent alone, so an
        unanswered question must not remove somebody from it; an explicit no
        must.
        """
        query = (
            select(MemberConsent.member_id, MemberConsent.granted, MemberConsent.recorded_at)
            .where(MemberConsent.tenant_id == self.tenant_id)
            .where(MemberConsent.kind == kind)
            .order_by(MemberConsent.recorded_at.desc(), MemberConsent.id.desc())
        )
        rows = (await self.session.execute(query)).all()

        newest: dict[uuid.UUID, bool] = {}
        for member_id, granted, _ in rows:
            if member_id not in newest:
                newest[member_id] = granted
        return {member_id for member_id, granted in newest.items() if not granted}
