"""The club's filing cabinet: folders and the documents in them.

Named `library` throughout, never `documents`: `documents` is the certificate
module, which *produces* files from templates. This module *keeps* files
somebody uploaded. The two are one careless rename away from being the same
table, and they are not the same thing at all.

Files *about a member* — a scanned application, a certificate of conduct —
are deliberately not here. Technically almost identical, legally not: those
carry their own retention periods and their own right to erasure, and they
must not end up on the same shelf as the statutes.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, SoftDeleteMixin, TenantModel

#: Who may see a document.
#:
#: - `board`  — the committee and above (`owner`, `admin`, `board`).
#: - `members` — everyone signed in to the club.
#:
#: Public (no login, for the club's website) is deliberately not a value: it
#: is a different promise with different consequences — indexing, bandwidth,
#: liability for photographs — and belongs decided rather than added in
#: passing. Per-division visibility is out of v1 for a smaller reason: it
#: doubles the check at every read and in every test, and two levels get a
#: club a long way.
LIBRARY_VISIBILITIES = ("board", "members")


class LibraryFolder(TenantModel, AuditMixin):
    """A drawer. Nests, because "Protokolle ▸ 2026" is what a club writes.

    Deleting is refused while anything is inside — a delete that quietly takes
    twenty files with it is not a delete anyone asked for. Moving is checked
    for cycles in the service; the database cannot see that a folder is about
    to become its own grandchild.
    """

    __tablename__ = "library_folders"
    __table_args__ = (
        # Two folders of the same name in the same drawer would be a filing
        # system that cannot answer where something is.
        #
        # `NULLS NOT DISTINCT` is what makes this hold at the root as well.
        # Without it the rule would quietly stop applying exactly there: in
        # SQL two NULLs are not equal, so `parent_id IS NULL` twice looks like
        # two different drawers and "Protokolle" could exist twice at the top
        # level. Postgres 15+, which the compose file pins anyway.
        UniqueConstraint(
            "tenant_id",
            "parent_id",
            "name",
            name="uq_library_folders_parent_name",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_library_folders_tenant_parent", "tenant_id", "parent_id"),
    )

    # RESTRICT: a folder with children is emptied first, deliberately.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("library_folders.id", ondelete="RESTRICT"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class LibraryDocument(TenantModel, AuditMixin, SoftDeleteMixin):
    """One filed document, in one version.

    **Versions without a second table.** A new edition of the statutes is a new
    row pointing at the old one through `replaces_id`, and the old row gets
    `superseded_at`. Lists show `superseded_at IS NULL`. That answers "which
    statutes applied in 2024" without a second model and a second read path.

    **The row outlives the bytes.** Deleting removes the blob immediately and
    marks the row `deleted_at`: the trail of who filed what and when is the
    point of a club archive, while an erasure request is about the content.
    `storage_key` on a deleted row therefore points at nothing, on purpose.
    """

    __tablename__ = "library_documents"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('board', 'members')",
            name="ck_library_documents_visibility",
        ),
        CheckConstraint("byte_size >= 0", name="ck_library_documents_byte_size"),
        Index("ix_library_documents_tenant_folder", "tenant_id", "folder_id"),
        # The list query: current versions of a club, newest first.
        Index("ix_library_documents_tenant_current", "tenant_id", "superseded_at"),
    )

    # RESTRICT rather than CASCADE: deleting a folder must not take the files
    # in it, and the service refuses long before the database has to.
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("library_folders.id", ondelete="RESTRICT"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="board")

    # `{tenant_id}/{uuid4}` — never a filename. See app/core/storage.py.
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # Kept for the download header and for recognition in a list. It is a
    # display value: nothing ever builds a path out of it.
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # Detected from the first bytes, not taken from the upload.
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # The version this one replaced, and the moment it stopped being current.
    replaces_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("library_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
