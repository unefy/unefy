import uuid
from collections.abc import Sequence

from sqlalchemy import Select, func, or_, select

from app.models.library import LibraryDocument, LibraryFolder
from app.repositories.base import BaseRepository
from app.schemas.library import (
    LibraryDocumentUpdate,
    LibraryFolderCreate,
    LibraryFolderUpdate,
)


class LibraryFolderRepository(
    BaseRepository[LibraryFolder, LibraryFolderCreate, LibraryFolderUpdate]
):
    model_class = LibraryFolder

    async def list_all(self) -> list[LibraryFolder]:
        """The whole tree, flat. A club's folder list is small enough to send
        in one piece, and the UI has to draw the tree anyway."""
        query = self._base_query().order_by(
            LibraryFolder.sort_order.asc(), LibraryFolder.name.asc()
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_name(self, *, parent_id: uuid.UUID | None, name: str) -> LibraryFolder | None:
        query = self._base_query().where(LibraryFolder.name == name)
        query = (
            query.where(LibraryFolder.parent_id.is_(None))
            if parent_id is None
            else query.where(LibraryFolder.parent_id == parent_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def child_count(self, folder_id: uuid.UUID) -> int:
        query = (
            select(func.count())
            .select_from(LibraryFolder)
            .where(LibraryFolder.tenant_id == self.tenant_id)
            .where(LibraryFolder.parent_id == folder_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one()


class LibraryDocumentRepository(
    BaseRepository[LibraryDocument, LibraryDocumentUpdate, LibraryDocumentUpdate]
):
    model_class = LibraryDocument

    def _visible(self, visibilities: Sequence[str]) -> Select[tuple[LibraryDocument]]:
        return self._base_query().where(LibraryDocument.visibility.in_(visibilities))

    async def get_visible(
        self, document_id: uuid.UUID, visibilities: Sequence[str]
    ) -> LibraryDocument | None:
        """A document the caller is allowed to see, or nothing.

        Nothing rather than a 403: a member asking for a committee document by
        id learns that it does not exist for them, which is the same answer
        they get for an id that never existed.
        """
        query = self._visible(visibilities).where(LibraryDocument.id == document_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_page(
        self,
        *,
        visibilities: Sequence[str],
        folder_id: uuid.UUID | None = None,
        search: str | None = None,
        include_superseded: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[LibraryDocument], int]:
        """One folder's contents, or the whole club when searching.

        Searching across folders is the point of searching — a search that only
        looks in the drawer already open is a filter, and the caller can do
        that themselves.
        """
        query = self._visible(visibilities)
        count_query = (
            select(func.count())
            .select_from(LibraryDocument)
            .where(LibraryDocument.tenant_id == self.tenant_id)
            .where(LibraryDocument.deleted_at.is_(None))
            .where(LibraryDocument.visibility.in_(visibilities))
        )

        if not include_superseded:
            query = query.where(LibraryDocument.superseded_at.is_(None))
            count_query = count_query.where(LibraryDocument.superseded_at.is_(None))

        if search:
            pattern = f"%{search.strip()}%"
            condition = or_(
                LibraryDocument.title.ilike(pattern),
                LibraryDocument.description.ilike(pattern),
                LibraryDocument.original_filename.ilike(pattern),
            )
            query = query.where(condition)
            count_query = count_query.where(condition)
        elif folder_id is None:
            query = query.where(LibraryDocument.folder_id.is_(None))
            count_query = count_query.where(LibraryDocument.folder_id.is_(None))
        else:
            query = query.where(LibraryDocument.folder_id == folder_id)
            count_query = count_query.where(LibraryDocument.folder_id == folder_id)

        query = query.order_by(LibraryDocument.uploaded_at.desc()).offset(offset).limit(limit)
        rows = (await self.session.execute(query)).scalars().all()
        total = (await self.session.execute(count_query)).scalar_one()
        return list(rows), total

    async def count_in_folder(self, folder_id: uuid.UUID) -> int:
        """Every document in the folder, including superseded versions.

        Not filtered by visibility on purpose: this answers "is the folder
        empty", and a folder holding a committee document is not empty just
        because the person asking cannot see it.
        """
        query = (
            select(func.count())
            .select_from(LibraryDocument)
            .where(LibraryDocument.tenant_id == self.tenant_id)
            .where(LibraryDocument.deleted_at.is_(None))
            .where(LibraryDocument.folder_id == folder_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one()

    async def total_bytes(self) -> int:
        """What the club currently occupies. Deleted rows do not count —
        their blobs are gone, so counting them would charge for nothing."""
        query = (
            select(func.coalesce(func.sum(LibraryDocument.byte_size), 0))
            .where(LibraryDocument.tenant_id == self.tenant_id)
            .where(LibraryDocument.deleted_at.is_(None))
        )
        result = await self.session.execute(query)
        return int(result.scalar_one())

    async def versions_of(self, document_id: uuid.UUID) -> list[LibraryDocument]:
        """The chain behind a document, newest first.

        Walked in Python rather than with a recursive CTE: the chain is a
        handful of rows, and each step is a primary-key lookup.
        """
        chain: list[LibraryDocument] = []
        current = await self.get_by_id(document_id)
        while current is not None:
            chain.append(current)
            if current.replaces_id is None:
                break
            current = await self.get_by_id(current.replaces_id)
        return chain
