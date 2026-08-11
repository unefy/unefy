import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

Visibility = Literal["board", "members"]


# --- Folders ---


class LibraryFolderCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    parent_id: uuid.UUID | None = None
    sort_order: int = 0


class LibraryFolderUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    # Explicit `null` moves the folder to the root, which is why every write
    # path reads this with `exclude_unset=True`: "not mentioned" and "moved to
    # the top" are different requests and must not collapse into one.
    parent_id: uuid.UUID | None = None
    sort_order: int | None = None


class LibraryFolderResponse(BaseSchema):
    id: uuid.UUID
    parent_id: uuid.UUID | None = None
    name: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


# --- Documents ---


class LibraryDocumentUpdate(BaseSchema):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    folder_id: uuid.UUID | None = None
    visibility: Visibility | None = None


class LibraryDocumentResponse(BaseSchema):
    id: uuid.UUID
    folder_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    visibility: Visibility
    original_filename: str
    content_type: str
    byte_size: int
    checksum_sha256: str
    uploaded_by_user_id: uuid.UUID | None = None
    uploaded_at: datetime
    replaces_id: uuid.UUID | None = None
    superseded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class LibraryUsageResponse(BaseSchema):
    """What the club has used and what it may use.

    The upload form needs all three before it lets someone pick a 40 MB scan
    and watch it fail at the end.
    """

    used_bytes: int
    quota_bytes: int
    max_upload_bytes: int
