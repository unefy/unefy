"""Push device rows: upsert by token, forget by token, fan-out lookups.

Not a `BaseRepository` subclass: the fan-out reads across a tenant without a
caller, and the one uniqueness that matters (the token) is global, because a
device that re-registers under a new account must *move* its row rather than
leave a second one behind that the old club keeps waking.
"""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.push_device import PushDevice


class PushDeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        token: str,
        platform: str,
        role: str,
    ) -> None:
        """Register or refresh. On conflict the row moves to the caller —
        tenant, user and role are overwritten, `last_seen_at` bumps."""
        statement = insert(PushDevice).values(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            token=token,
            platform=platform,
            role=role,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[PushDevice.token],
            set_={
                "tenant_id": tenant_id,
                "user_id": user_id,
                "platform": platform,
                "role": role,
                "last_seen_at": func.now(),
            },
        )
        await self.session.execute(statement)

    async def delete_by_token(self, token: str) -> bool:
        """Forget a device. Possessing the token is the proof of ownership —
        it never leaves the device except toward this endpoint."""
        result = await self.session.execute(delete(PushDevice).where(PushDevice.token == token))
        return bool(result.rowcount)  # type: ignore[attr-defined]  # CursorResult at runtime

    async def tokens_for_roles(self, tenant_id: uuid.UUID, roles: tuple[str, ...]) -> list[str]:
        """Every token in the club whose stored role is one of `roles`."""
        result = await self.session.execute(
            select(PushDevice.token)
            .where(PushDevice.tenant_id == tenant_id)
            .where(PushDevice.role.in_(roles))
        )
        return list(result.scalars().all())
