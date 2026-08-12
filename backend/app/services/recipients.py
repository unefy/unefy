"""Turning "the board", "everyone" or "who owes for 2026" into addresses.

This is the part of the round mail that can be quietly wrong. Everything else
fails loudly — a mail server refuses, a screen shows an error — but a selection
that resolves to 143 people when it should be 155 sends a perfectly successful
message to the wrong list, and nobody finds out until the twelve who were
missed say they never heard about the meeting.

So it lives on its own, ahead of any sending, and answers three questions
separately:

1. **Who is meant** — one query per kind of selection.
2. **Who can be reached** — a member without an address is skipped, not failed.
3. **Who may be written to** — consent applies to `newsletter` and not to
   `notice`, because an invitation to the general meeting is an obligation and
   not a mailing.

The third question has three answers and not two. A member who said no and a
member nobody ever asked are both skipped, and telling them apart is the one
number on the screen a club can act on: ask the second group.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, extract, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.due import Due
from app.models.event import EventRegistration
from app.models.function import MemberFunction
from app.models.member import Member
from app.models.tenant import Tenant
from app.repositories.consent import newest_answers
from app.schemas.message import Audience, AudienceSummary, MessageKind

#: The consent a newsletter needs. One of `CONSENT_KINDS`.
NEWSLETTER_CONSENT = "newsletter"

SkipReason = Literal["no_email", "refused", "not_asked"]


@dataclass(frozen=True, slots=True)
class ResolvedRecipient:
    """One member, and whether the message will reach them."""

    member_id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None
    status: Literal["pending", "skipped"]
    reason: SkipReason | None = None


def decide(
    *,
    email: str | None,
    consent: bool | None,
    kind: MessageKind,
) -> tuple[Literal["pending", "skipped"], SkipReason | None]:
    """Whether this member gets the message, and if not, why not.

    `consent` is three-valued on purpose: `True` given, `False` refused, `None`
    never asked. Collapsing the last two would delete exactly the distinction
    the consent ledger exists to keep (see 6.2 in the roadmap).

    Pure, and tested as such: this is the rule the whole module rests on, and
    it should be readable without a database in the room.
    """
    if not email or "@" not in email:
        return "skipped", "no_email"
    if kind == "newsletter":
        if consent is False:
            return "skipped", "refused"
        if consent is None:
            return "skipped", "not_asked"
    return "pending", None


def summarize(recipients: list[ResolvedRecipient]) -> AudienceSummary:
    """The counts the compose screen shows before anything goes out."""
    return AudienceSummary(
        total=len(recipients),
        pending=sum(1 for r in recipients if r.status == "pending"),
        skipped_no_email=sum(1 for r in recipients if r.reason == "no_email"),
        skipped_refused=sum(1 for r in recipients if r.reason == "refused"),
        skipped_not_asked=sum(1 for r in recipients if r.reason == "not_asked"),
    )


class RecipientResolver:
    """Resolves an audience against one club's data. Never writes anything."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def resolve(
        self,
        audience: Audience,
        kind: MessageKind,
        *,
        today: date | None = None,
    ) -> list[ResolvedRecipient]:
        """Everyone the selection means, each with their outcome.

        Skipped members are returned rather than dropped. A list that silently
        contains only the reachable people cannot answer "why 143 and not 155",
        which is the first thing anybody asks.
        """
        members = (await self.session.execute(await self._query(audience, today))).scalars().all()
        consents = await self._consents()

        return [
            ResolvedRecipient(
                member_id=member.id,
                first_name=member.first_name,
                last_name=member.last_name,
                email=member.email,
                status=status,
                reason=reason,
            )
            for member in members
            for status, reason in [
                decide(email=member.email, consent=consents.get(member.id), kind=kind)
            ]
        ]

    async def _consents(self) -> dict[uuid.UUID, bool]:
        """The newest newsletter answer per member. Absent means never asked."""
        rows = await self.session.execute(newest_answers(self.tenant_id, NEWSLETTER_CONSENT))
        return {member_id: granted for member_id, granted in rows.all()}

    async def _today(self) -> date:
        """The club's day, not the server's.

        An office that ends today ends at midnight where the club is, and a
        server in UTC would drop its holder from the board list two hours
        early — or keep them two hours too long.
        """
        tenant = await self.session.get(Tenant, self.tenant_id)
        zone = ZoneInfo(tenant.timezone if tenant else "Europe/Berlin")
        return datetime.now(zone).date()

    def _base(self) -> Select[tuple[Member]]:
        return (
            select(Member)
            .where(Member.tenant_id == self.tenant_id)
            .where(Member.deleted_at.is_(None))
            .order_by(Member.last_name, Member.first_name)
        )

    async def _query(self, audience: Audience, today: date | None) -> Select[tuple[Member]]:
        match audience.type:
            case "all":
                # Former members are not written to. They left; a club that
                # keeps mailing them is the reason people ask to be deleted.
                return self._base().where(Member.status == "active")

            case "function":
                effective = today or await self._today()
                return (
                    self._base()
                    .join(MemberFunction, MemberFunction.member_id == Member.id)
                    .where(MemberFunction.tenant_id == self.tenant_id)
                    .where(MemberFunction.function_id == audience.id)
                    .where(MemberFunction.valid_from <= effective)
                    .where(
                        or_(
                            MemberFunction.valid_to.is_(None),
                            MemberFunction.valid_to >= effective,
                        )
                    )
                    # A member can hold the same office twice over (two terms
                    # that meet); the mail still goes out once.
                    .distinct()
                )

            case "event":
                states = ["registered", "waitlist"] if audience.include_waitlist else ["registered"]
                return (
                    self._base()
                    .join(EventRegistration, EventRegistration.member_id == Member.id)
                    .where(EventRegistration.tenant_id == self.tenant_id)
                    .where(EventRegistration.event_id == audience.id)
                    .where(EventRegistration.deleted_at.is_(None))
                    .where(EventRegistration.status.in_(states))
                    .distinct()
                )

            case "debtors":
                # Open assessments whose billing period starts in that year.
                # `period_start`, not `due_date`: the year a club means is the
                # year the fee is for, and a December assessment due in January
                # belongs to the former.
                return (
                    self._base()
                    .join(Due, Due.member_id == Member.id)
                    .where(
                        and_(
                            Due.tenant_id == self.tenant_id,
                            Due.deleted_at.is_(None),
                            Due.status == "open",
                            extract("year", Due.period_start) == audience.year,
                        )
                    )
                    # One member with four unpaid quarters is one recipient.
                    .distinct()
                )
