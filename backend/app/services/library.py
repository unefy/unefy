"""Filing, finding and removing the club's documents.

The rules that live here rather than in the database or the endpoint:

- **A folder is emptied before it is deleted.** Not because the foreign key
  says so — it does too — but because a delete that silently takes twenty
  files with it is not the delete anyone meant.
- **A folder never moves inside itself.** The database cannot see that the
  drawer being moved is an ancestor of its new home; three rows would simply
  point at each other and disappear from the tree.
- **The bytes decide the type, and the quota is checked before them.** An
  upload that is refused must be refused before anything is written, or the
  refusal is a receipt for the disk space it just used.
- **Deleting deletes.** The blob goes immediately; the row stays as a
  tombstone so the trail of who filed what survives.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    ValidationError,
)
from app.core.file_types import UnsupportedFileTypeError, detect_content_type
from app.core.storage import ObjectTooLargeError, Storage, build_key
from app.dependencies import AuthContext
from app.models.library import LibraryDocument, LibraryFolder
from app.repositories.library import LibraryDocumentRepository, LibraryFolderRepository
from app.schemas.library import (
    LibraryDocumentUpdate,
    LibraryFolderCreate,
    LibraryFolderUpdate,
)
from app.services.audit import diff, jsonable, record_tenant_action

#: Roles that may write, and that see everything.
BOARD_ROLES = ("owner", "admin", "board")

#: Audited: filing, removing and changing who may see something. Renaming a
#: folder is not — a log nobody reads is noise, and the trail exists for the
#: three actions that change what a club holds and who can read it.
DOCUMENT_TARGET = "library_document"

#: How deep the tree may go. Not a technical limit — a guard against a client
#: that builds a chain of a thousand folders and turns every ancestor walk
#: into a thousand queries.
MAX_FOLDER_DEPTH = 20


@dataclass(frozen=True)
class IncomingFile:
    """An upload, reduced to what the service needs.

    `head` is the first few kilobytes, already read, so the type can be
    decided before a single byte is stored. `stream` yields the *whole* file
    including that head — the endpoint rewinds before handing it over.
    """

    filename: str
    head: bytes
    stream: AsyncIterator[bytes]
    declared_size: int | None = None


class LibraryService:
    def __init__(self, session: AsyncSession, auth: AuthContext, storage: Storage) -> None:
        self.session = session
        self.auth = auth
        self.tenant_id = auth.tenant
        self.storage = storage
        self.folders = LibraryFolderRepository(session, self.tenant_id)
        self.documents = LibraryDocumentRepository(session, self.tenant_id)

    @property
    def visibilities(self) -> tuple[str, ...]:
        """What this caller is allowed to see.

        The committee sees both levels, a member sees only what is meant for
        members. This is the whole of the visibility rule, in one place — every
        read path goes through it rather than restating it.
        """
        return ("board", "members") if self.auth.role in BOARD_ROLES else ("members",)

    # --- Folders ---

    async def list_folders(self) -> list[LibraryFolder]:
        return await self.folders.list_all()

    async def get_folder(self, folder_id: uuid.UUID) -> LibraryFolder:
        folder = await self.folders.get_by_id(folder_id)
        if folder is None:
            raise NotFoundError("Folder not found")
        return folder

    async def create_folder(self, data: LibraryFolderCreate) -> LibraryFolder:
        if data.parent_id is not None:
            await self.get_folder(data.parent_id)
            if await self._depth_of(data.parent_id) >= MAX_FOLDER_DEPTH:
                raise ValidationError(f"Folders may not nest deeper than {MAX_FOLDER_DEPTH} levels")
        await self._require_free_name(parent_id=data.parent_id, name=data.name)

        folder = LibraryFolder(
            name=data.name,
            parent_id=data.parent_id,
            sort_order=data.sort_order,
            tenant_id=self.tenant_id,
            created_by=self.auth.user_id,
            updated_by=self.auth.user_id,
        )
        self.session.add(folder)
        await self.session.flush()
        await self.session.refresh(folder)
        return folder

    async def update_folder(self, folder_id: uuid.UUID, data: LibraryFolderUpdate) -> LibraryFolder:
        folder = await self.get_folder(folder_id)
        fields = data.model_dump(exclude_unset=True)

        new_parent = fields.get("parent_id", folder.parent_id)
        new_name = fields.get("name", folder.name)

        if "parent_id" in fields and new_parent != folder.parent_id:
            await self._check_move(folder, new_parent)
        if new_parent != folder.parent_id or new_name != folder.name:
            await self._require_free_name(parent_id=new_parent, name=new_name, except_id=folder.id)

        for field, value in fields.items():
            setattr(folder, field, value)
        folder.updated_by = self.auth.user_id
        await self.session.flush()
        await self.session.refresh(folder)
        return folder

    async def delete_folder(self, folder_id: uuid.UUID) -> None:
        folder = await self.get_folder(folder_id)
        if await self.folders.child_count(folder.id) > 0:
            raise ConflictError("This folder still contains folders")
        if await self.documents.count_in_folder(folder.id) > 0:
            raise ConflictError("This folder still contains documents")
        await self.session.delete(folder)
        await self.session.flush()

    # --- Documents ---

    async def list_documents(
        self,
        *,
        folder_id: uuid.UUID | None = None,
        search: str | None = None,
        include_superseded: bool = False,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[LibraryDocument], int]:
        if folder_id is not None and not search:
            await self.get_folder(folder_id)
        return await self.documents.list_page(
            visibilities=self.visibilities,
            folder_id=folder_id,
            search=search,
            include_superseded=include_superseded,
            offset=(page - 1) * per_page,
            limit=per_page,
        )

    async def get_document(self, document_id: uuid.UUID) -> LibraryDocument:
        document = await self.documents.get_visible(document_id, self.visibilities)
        if document is None:
            raise NotFoundError("Document not found")
        return document

    async def versions(self, document_id: uuid.UUID) -> list[LibraryDocument]:
        # Through `get_document` first: the chain of a document the caller
        # cannot see must not be readable by asking for its history instead.
        await self.get_document(document_id)
        return await self.documents.versions_of(document_id)

    async def upload(
        self,
        file: IncomingFile,
        *,
        title: str,
        description: str | None = None,
        folder_id: uuid.UUID | None = None,
        visibility: str = "board",
        settings: Settings,
        request: Request | None = None,
    ) -> LibraryDocument:
        if folder_id is not None:
            await self.get_folder(folder_id)
        document = await self._store(
            file,
            title=title,
            description=description,
            folder_id=folder_id,
            visibility=visibility,
            settings=settings,
        )
        await record_tenant_action(
            self.session,
            self.auth,
            f"{DOCUMENT_TARGET}.uploaded",
            target_type=DOCUMENT_TARGET,
            target_id=document.id,
            request=request,
            changes={
                "title": document.title,
                "filename": document.original_filename,
                "content_type": document.content_type,
                "byte_size": document.byte_size,
                "visibility": document.visibility,
            },
        )
        return document

    async def add_version(
        self,
        document_id: uuid.UUID,
        file: IncomingFile,
        *,
        title: str | None = None,
        description: str | None = None,
        settings: Settings,
        request: Request | None = None,
    ) -> LibraryDocument:
        """File a new edition of a document that is already in the library.

        The predecessor keeps its row and its bytes — "which statutes applied
        in 2024" is exactly the question this answers — and stops appearing in
        the list. Filing a version of an already superseded document is
        refused: two current successors of one predecessor is a fork, and a
        filing cabinet has no way to show one.
        """
        previous = await self.get_document(document_id)
        if previous.superseded_at is not None:
            raise ConflictError(
                "This version has already been replaced. Add the new version to the current one."
            )

        document = await self._store(
            file,
            title=title or previous.title,
            description=previous.description if description is None else description,
            folder_id=previous.folder_id,
            visibility=previous.visibility,
            settings=settings,
            replaces=previous,
        )
        previous.superseded_at = document.uploaded_at
        previous.updated_by = self.auth.user_id
        await self.session.flush()

        await record_tenant_action(
            self.session,
            self.auth,
            f"{DOCUMENT_TARGET}.version_added",
            target_type=DOCUMENT_TARGET,
            target_id=document.id,
            request=request,
            changes={
                "replaces_id": str(previous.id),
                "filename": document.original_filename,
                "byte_size": document.byte_size,
            },
        )
        return document

    async def update_document(
        self,
        document_id: uuid.UUID,
        data: LibraryDocumentUpdate,
        *,
        request: Request | None = None,
    ) -> LibraryDocument:
        document = await self.get_document(document_id)
        fields = data.model_dump(exclude_unset=True)

        if "folder_id" in fields and fields["folder_id"] is not None:
            await self.get_folder(fields["folder_id"])

        before = {field: getattr(document, field) for field in fields}
        for field, value in fields.items():
            setattr(document, field, value)
        document.updated_by = self.auth.user_id
        await self.session.flush()
        await self.session.refresh(document)

        applied = diff(before, {k: jsonable(v) for k, v in fields.items()})
        if applied:
            await record_tenant_action(
                self.session,
                self.auth,
                # A change of visibility is the one edit here with a security
                # meaning, so it is named as itself rather than folded into a
                # generic "updated" that nobody scans the log for.
                f"{DOCUMENT_TARGET}."
                + ("visibility_changed" if "visibility" in fields else "updated"),
                target_type=DOCUMENT_TARGET,
                target_id=document.id,
                request=request,
                changes=applied,
            )
        return document

    async def delete_document(
        self, document_id: uuid.UUID, *, request: Request | None = None
    ) -> None:
        """Remove the bytes now, keep the row as a tombstone.

        The blob goes first. If the row update then fails the transaction rolls
        back and the row survives pointing at nothing, which is visible and
        fixable; the other order can leave a file on disk that nothing in the
        database mentions and nobody will ever find again.
        """
        document = await self.get_document(document_id)
        await self.storage.delete(document.storage_key)

        # A newer version may point here through `replaces_id`. The chain walk
        # stops at a deleted row of its own accord, so the history simply ends
        # where the club decided it should end.
        document.deleted_at = datetime.now(UTC)
        document.updated_by = self.auth.user_id
        await self.session.flush()

        await record_tenant_action(
            self.session,
            self.auth,
            f"{DOCUMENT_TARGET}.deleted",
            target_type=DOCUMENT_TARGET,
            target_id=document.id,
            request=request,
            changes={"title": document.title, "filename": document.original_filename},
        )

    def open_content(self, document: LibraryDocument) -> AsyncIterator[bytes]:
        return self.storage.open(document.storage_key)

    async def usage(self, settings: Settings) -> tuple[int, int]:
        return await self.documents.total_bytes(), settings.TENANT_STORAGE_QUOTA_BYTES

    # --- Helpers ---

    async def _store(
        self,
        file: IncomingFile,
        *,
        title: str,
        description: str | None,
        folder_id: uuid.UUID | None,
        visibility: str,
        settings: Settings,
        replaces: LibraryDocument | None = None,
    ) -> LibraryDocument:
        """Type, size and quota, then the bytes, then the row.

        In that order, deliberately. Each check that runs before the write is a
        refusal that costs nothing; a quota checked afterwards would be a
        message saying the club is out of space, sent from the request that
        used the last of it.
        """
        try:
            content_type = detect_content_type(file.head, file.filename)
        except UnsupportedFileTypeError as exc:
            raise UnsupportedMediaTypeError(str(exc)) from exc

        max_upload = settings.MAX_UPLOAD_BYTES
        used, quota = await self.usage(settings)
        remaining = max(quota - used, 0)

        if file.declared_size is not None and file.declared_size > max_upload:
            raise PayloadTooLargeError(
                f"The file is larger than the limit of {max_upload} bytes",
                code="UPLOAD_TOO_LARGE",
            )
        if file.declared_size is not None and file.declared_size > remaining:
            raise PayloadTooLargeError(
                "The club's storage quota is exhausted", code="STORAGE_QUOTA_EXCEEDED"
            )

        key = build_key(self.tenant_id)
        try:
            # The ceiling the writer enforces is the stricter of the two, so a
            # client that understates its size runs into the same wall.
            stored = await self.storage.put(key, file.stream, max_bytes=min(max_upload, remaining))
        except ObjectTooLargeError as exc:
            if remaining <= max_upload:
                raise PayloadTooLargeError(
                    "The club's storage quota is exhausted", code="STORAGE_QUOTA_EXCEEDED"
                ) from exc
            raise PayloadTooLargeError(
                f"The file is larger than the limit of {max_upload} bytes",
                code="UPLOAD_TOO_LARGE",
            ) from exc

        now = datetime.now(UTC)
        document = LibraryDocument(
            tenant_id=self.tenant_id,
            folder_id=folder_id,
            title=title,
            description=description,
            visibility=visibility,
            storage_key=stored.key,
            original_filename=_display_filename(file.filename),
            content_type=content_type,
            byte_size=stored.byte_size,
            checksum_sha256=stored.checksum_sha256,
            uploaded_by_user_id=self.auth.user_id,
            uploaded_at=now,
            replaces_id=replaces.id if replaces else None,
            created_by=self.auth.user_id,
            updated_by=self.auth.user_id,
        )
        self.session.add(document)
        try:
            await self.session.flush()
        except Exception:
            # The row never happened, so the blob must not survive it: an
            # orphan under a key nothing references is invisible to every list
            # and to the quota, and only ever grows.
            await self.storage.delete(stored.key)
            raise
        await self.session.refresh(document)
        return document

    async def _require_free_name(
        self, *, parent_id: uuid.UUID | None, name: str, except_id: uuid.UUID | None = None
    ) -> None:
        existing = await self.folders.get_by_name(parent_id=parent_id, name=name)
        if existing is not None and existing.id != except_id:
            raise ConflictError("A folder with this name already exists here")

    async def _check_move(self, folder: LibraryFolder, new_parent_id: uuid.UUID | None) -> None:
        """A folder may not become its own descendant.

        Walked upwards from the intended new parent: if this folder turns up on
        the way to the root, the move would cut the branch off the tree — the
        rows would keep pointing at each other and nothing would ever list them
        again.
        """
        if new_parent_id is None:
            return
        if new_parent_id == folder.id:
            raise ValidationError("A folder cannot be moved into itself")

        current: uuid.UUID | None = new_parent_id
        for _ in range(MAX_FOLDER_DEPTH + 1):
            if current is None:
                return
            parent = await self.get_folder(current)
            if parent.id == folder.id:
                raise ValidationError("A folder cannot be moved into one of its own subfolders")
            current = parent.parent_id
        raise ValidationError(f"Folders may not nest deeper than {MAX_FOLDER_DEPTH} levels")

    async def _depth_of(self, folder_id: uuid.UUID) -> int:
        depth = 1
        current = (await self.get_folder(folder_id)).parent_id
        while current is not None and depth <= MAX_FOLDER_DEPTH:
            depth += 1
            current = (await self.get_folder(current)).parent_id
        return depth


def _display_filename(filename: str) -> str:
    """The name as a name: no directories, and short enough for the column.

    Nothing builds a path from this — the storage key does that — so the point
    here is only that a list stays readable and a `Content-Disposition` header
    stays parseable.
    """
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    name = name.replace("\r", "").replace("\n", "").replace('"', "")
    return (name or "dokument")[:255]
