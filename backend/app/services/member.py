import re
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.models.member import Member
from app.models.tenant import Tenant
from app.repositories.member import MemberRepository
from app.schemas.member import MemberCreate, MemberUpdate


def format_member_number(fmt: str, num: int) -> str:
    """Generate member number from format template."""
    year = str(datetime.now(UTC).year)
    result = fmt

    result = result.replace("{YEAR}", year)

    # Handle {NUM:N} with zero-padding
    num_match = re.search(r"\{NUM:([1-9])\}", result)
    if num_match:
        pad = int(num_match.group(1))
        result = re.sub(r"\{NUM:[1-9]\}", str(num).zfill(pad), result)

    # Handle plain {NUM}
    result = result.replace("{NUM}", str(num))

    return result


class MemberService:
    """Service for member operations with business logic."""

    def __init__(self, repository: MemberRepository, session: AsyncSession) -> None:
        self.repository = repository
        self.session = session

    async def get(self, member_id: uuid.UUID) -> Member | None:
        return await self.repository.get_by_id(member_id)

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: str | None = None,
        category: str | None = None,
        search: str | None = None,
        sort_by: str = "last_name",
        sort_order: str = "asc",
    ) -> list[Member]:
        return await self.repository.get_all(
            offset=offset,
            limit=limit,
            status=status,
            category=category,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def count(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> int:
        return await self.repository.count(
            status=status,
            category=category,
            search=search,
        )

    async def status_counts(
        self,
        *,
        search: str | None = None,
    ) -> dict[str, int]:
        return await self.repository.status_counts(search=search)

    async def create(self, data: MemberCreate, created_by: uuid.UUID) -> Member:
        """Create a member with auto-generated member number.

        Idempotent when the caller supplies `data.id`: sending the same id twice
        returns the member created the first time rather than a second one. An
        offline client retries a request whose reply it never saw, and doing
        that must not put the same person in the club twice.
        """
        fields = data.model_dump(exclude_unset=False)
        member_id = fields.pop("id", None)

        if member_id is not None:
            # Before the tenant lock, so a replay does not queue behind every
            # other creation in the club just to discover it has nothing to do.
            # Only a shortcut, though — the `IntegrityError` branch below is
            # what actually makes this safe against two replays at once.
            existing = await self.repository.get_by_id(member_id)
            if existing is not None:
                return existing

        # Lock tenant row to prevent race conditions on member_number_next
        stmt = select(Tenant).where(Tenant.id == self.repository.tenant_id).with_for_update()
        result = await self.session.execute(stmt)
        tenant = result.scalar_one()

        # Generate member number
        member_number = format_member_number(
            tenant.member_number_format,
            tenant.member_number_next,
        )

        if not fields.get("joined_at"):
            fields["joined_at"] = date.today()

        member = Member(
            **fields,
            tenant_id=self.repository.tenant_id,
            member_number=member_number,
            created_by=created_by,
            updated_by=created_by,
        )
        if member_id is not None:
            member.id = member_id

        # Increment next number
        tenant.member_number_next += 1

        try:
            # A savepoint, not the request transaction: a rollback of the outer
            # transaction here would throw away the audit row and anything else
            # this request had already written, to recover from a duplicate this
            # method exists to tolerate.
            #
            # `add` belongs inside the savepoint. Added outside it, the pending
            # member survives the rollback and the very next query autoflushes
            # it again — the same INSERT, the same violation, and this time
            # nothing catching it.
            async with self.session.begin_nested():
                self.session.add(member)
                await self.session.flush()
        except IntegrityError:
            # Two replays of the same id arriving at once — the loser reads the
            # winner's row. The member number the loser reserved may stay spent;
            # a gap in the numbering is the cheap half of this trade, and
            # soft-deleted members leave gaps anyway.
            if member_id is None:
                raise
            existing = await self.repository.get_by_id(member_id)
            if existing is None:
                # The id is taken, but not by a member of this club: the lookup
                # above is tenant-scoped, the primary key is not. Answering 409
                # rather than letting a 500 out keeps it an ordinary refusal —
                # and says no more about the other club's data than the failure
                # itself already does.
                raise ConflictError("Member id already in use", code="ID_IN_USE") from None
            return existing

        await self.session.refresh(member)
        return member

    async def update(
        self,
        member_id: uuid.UUID,
        data: MemberUpdate,
        updated_by: uuid.UUID,
    ) -> Member | None:
        member = await self.repository.get_by_id(member_id)
        if member is None:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(member, field, value)
        member.updated_by = updated_by

        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def delete(self, member_id: uuid.UUID) -> bool:
        return await self.repository.soft_delete(member_id)

    async def delete_many(self, member_ids: Sequence[uuid.UUID]) -> int:
        """Soft-delete many members. Returns number actually deleted."""
        return await self.repository.soft_delete_many(member_ids)
