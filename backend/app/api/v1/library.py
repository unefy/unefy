"""`/api/v1/library` — the club's filing cabinet.

Reading is open to every member and filtered by visibility; writing is the
committee's. The one endpoint that is not JSON is the upload, which takes
multipart because a scan does not fit in a JSON body, and the one that is not
JSON coming back is the download, which streams.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.file_types import HEAD_BYTES
from app.core.storage import CHUNK_SIZE, Storage, get_storage
from app.database import get_db_session
from app.dependencies import AuthContext, get_current_user, require_role
from app.models.library import LibraryDocument
from app.schemas.library import (
    LibraryDocumentResponse,
    LibraryDocumentUpdate,
    LibraryFolderCreate,
    LibraryFolderResponse,
    LibraryFolderUpdate,
    LibraryUsageResponse,
)
from app.services.library import IncomingFile, LibraryService

router = APIRouter()

#: Types a browser can display safely from our own origin. Everything else is
#: sent as an attachment — SVG is not on the accepted list at all, and nothing
#: here is ever served with a type the uploader chose.
_INLINE_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "text/plain",
}


def _service(
    auth: AuthContext,
    session: AsyncSession,
    storage: Storage,
) -> LibraryService:
    return LibraryService(session, auth, storage)


def _document(document: LibraryDocument) -> dict[str, Any]:
    return LibraryDocumentResponse.model_validate(document).model_dump(mode="json")


# --- Folders ---


@router.get("/folders")
async def list_folders(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> dict[str, Any]:
    """The whole tree, flat. Folder names are not secret — what is in them is."""
    folders = await _service(auth, session, storage).list_folders()
    return {
        "data": [LibraryFolderResponse.model_validate(f).model_dump(mode="json") for f in folders]
    }


@router.post("/folders", status_code=201)
async def create_folder(
    data: LibraryFolderCreate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> dict[str, Any]:
    folder = await _service(auth, session, storage).create_folder(data)
    return {"data": LibraryFolderResponse.model_validate(folder).model_dump(mode="json")}


@router.patch("/folders/{folder_id}")
async def update_folder(
    folder_id: uuid.UUID,
    data: LibraryFolderUpdate,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> dict[str, Any]:
    """Rename, reorder or move. Moving a folder into itself is refused."""
    folder = await _service(auth, session, storage).update_folder(folder_id, data)
    return {"data": LibraryFolderResponse.model_validate(folder).model_dump(mode="json")}


@router.delete("/folders/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: uuid.UUID,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> None:
    """Only when empty — 409 otherwise, listing what is still inside."""
    await _service(auth, session, storage).delete_folder(folder_id)


# --- Documents ---


@router.get("/documents")
async def list_documents(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
    folder_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    search: str | None = Query(default=None, max_length=200),
    include_superseded: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """One folder's contents, or the whole club when `search` is given.

    Without `folder_id` this is the root, not everything: the library is a
    filing cabinet, and opening it shows the top drawer, not every sheet at
    once.
    """
    service = _service(auth, session, storage)
    documents, total = await service.list_documents(
        folder_id=folder_id,
        search=search,
        include_superseded=include_superseded,
        page=page,
        per_page=per_page,
    )
    return {
        "data": [_document(d) for d in documents],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        },
    }


@router.get("/usage")
async def storage_usage(
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """What is used and what may be used, so the form can say so up front."""
    used, quota = await _service(auth, session, storage).usage(settings)
    return {
        "data": LibraryUsageResponse(
            used_bytes=used,
            quota_bytes=quota,
            max_upload_bytes=settings.MAX_UPLOAD_BYTES,
        ).model_dump(mode="json")
    }


@router.post("/documents", status_code=201)
async def upload_document(
    request: Request,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    description: Annotated[str | None, Form(max_length=5000)] = None,
    folder_id: Annotated[uuid.UUID | None, Form()] = None,
    visibility: Annotated[str, Form(pattern="^(board|members)$")] = "board",
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """File a document. Multipart, because a scan does not fit in JSON."""
    service = _service(auth, session, storage)
    document = await service.upload(
        await _incoming(file),
        title=title,
        description=description,
        folder_id=folder_id,
        visibility=visibility,
        settings=settings,
        request=request,
    )
    return {"data": _document(document)}


@router.post("/documents/{document_id}/version", status_code=201)
async def upload_version(
    document_id: uuid.UUID,
    request: Request,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form(max_length=255)] = None,
    description: Annotated[str | None, Form(max_length=5000)] = None,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, Any]:
    """A new edition of the same document, in the same place.

    Folder and visibility come from the predecessor: a new version of the
    statutes is the same document, and re-deciding where it lives on every
    upload is how the second copy ends up somewhere else.
    """
    service = _service(auth, session, storage)
    document = await service.add_version(
        document_id,
        await _incoming(file),
        title=title,
        description=description,
        settings=settings,
        request=request,
    )
    return {"data": _document(document)}


@router.get("/documents/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> dict[str, Any]:
    document = await _service(auth, session, storage).get_document(document_id)
    return {"data": _document(document)}


@router.get("/documents/{document_id}/versions")
async def list_versions(
    document_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> dict[str, Any]:
    """This version and everything it replaced, newest first."""
    versions = await _service(auth, session, storage).versions(document_id)
    return {"data": [_document(d) for d in versions]}


@router.get("/documents/{document_id}/content")
async def download_document(
    document_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> StreamingResponse:
    """The bytes, streamed, once the row says this caller may have them.

    Every download passes through here — there are no public buckets and no
    guessable URLs, so authorisation stays on the one path it is written on.
    """
    service = _service(auth, session, storage)
    document = await service.get_document(document_id)

    disposition = "inline" if document.content_type in _INLINE_TYPES else "attachment"
    return StreamingResponse(
        service.open_content(document),
        media_type=document.content_type,
        headers={
            "Content-Disposition": (
                f'{disposition}; filename="{_ascii_filename(document.original_filename)}"; '
                f"filename*=UTF-8''{quote(document.original_filename)}"
            ),
            "Content-Length": str(document.byte_size),
            # The type is the detected one, and this stops a browser looking
            # for a better idea in the bytes — the two together are what keeps
            # an uploaded file from being run as something else.
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.patch("/documents/{document_id}")
async def update_document(
    document_id: uuid.UUID,
    data: LibraryDocumentUpdate,
    request: Request,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> dict[str, Any]:
    """Title, description, folder, visibility. Never the bytes — those are a
    new version, so that what was filed stays what was filed."""
    document = await _service(auth, session, storage).update_document(
        document_id, data, request=request
    )
    return {"data": _document(document)}


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    storage: Storage = Depends(get_storage),  # noqa: B008
) -> None:
    """Removes the file itself, not only the entry."""
    await _service(auth, session, storage).delete_document(document_id, request=request)


# --- Helpers ---


async def _incoming(file: UploadFile) -> IncomingFile:
    """Turn an upload into something the service can read twice over.

    The head is read first so the type can be decided before anything is
    stored, then the file is rewound and handed over whole. Starlette has
    already spooled it to a temporary file by this point, which is why reading
    it twice is cheap and why the size is known in advance.
    """
    head = await file.read(HEAD_BYTES)
    await file.seek(0)
    return IncomingFile(
        filename=file.filename or "dokument",
        head=head,
        stream=_chunks(file),
        declared_size=file.size,
    )


async def _chunks(file: UploadFile) -> AsyncIterator[bytes]:
    while chunk := await file.read(CHUNK_SIZE):
        yield chunk


def _ascii_filename(value: str) -> str:
    """The fallback name, for clients that ignore RFC 5987.

    Umlauts in a bare `filename=` are read differently by different clients, so
    the plain form stays ASCII and `filename*` carries the real name.
    """
    safe = "".join(c if c.isascii() and (c.isalnum() or c in "-_.") else "-" for c in value)
    return safe.strip("-") or "dokument"
