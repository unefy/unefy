"""How many bytes a club occupies, across everything that stores files.

One function, in its own module, because the answer must not depend on which
feature is asking. The quota is a club's share of a disk; a library that
reports 3% used while the invoice register has filled the volume would be
telling the truth about itself and lying about the club.

Every new feature that writes into `core.storage` belongs in the sum here, and
that is the whole reason this is not a method on one of the services.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incoming_invoice import IncomingInvoice
from app.models.library import LibraryDocument


async def stored_bytes(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    """What the club currently occupies.

    Soft-deleted rows do not count: their blobs are gone, so charging for them
    would bill a club for space it cannot free.
    """
    total = 0
    for model in (LibraryDocument, IncomingInvoice):
        query = (
            select(func.coalesce(func.sum(model.byte_size), 0))
            .where(model.tenant_id == tenant_id)
            .where(model.deleted_at.is_(None))
        )
        result = await session.execute(query)
        total += int(result.scalar_one())
    return total
