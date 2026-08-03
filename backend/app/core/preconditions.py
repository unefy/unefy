"""Optimistic concurrency without a version column.

Every model already carries `updated_at`, and that is the version: the ETag of
a resource is its `updated_at`, quoted. A client that wants lost-update
protection sends the ETag it last saw as `If-Match`; a mismatch answers 412
**with the current server representation in the error body**, so the client
resolves the conflict in one round trip instead of two.

Additive on purpose: no `If-Match` means exactly today's last-write-wins, so
the web app changes nothing until it wants to. And no `version = version + 1`
in every write path — `soft_delete_many` provably forgot that once already;
`updated_at` is maintained by SQLAlchemy itself.
"""

from datetime import datetime
from typing import Any, Protocol

from fastapi import Request, Response

from app.core.exceptions import AppError


class _HasUpdatedAt(Protocol):
    updated_at: datetime


class PreconditionFailedError(AppError):
    """The row moved since the client last read it."""

    def __init__(self, current: dict[str, Any]) -> None:
        super().__init__(
            status_code=412,
            code="PRECONDITION_FAILED",
            message="The resource changed since it was last read",
            # The current state rides along so the client can show a merge or
            # an overwrite prompt without a second request.
            details=[{"current": current}],
        )


def etag_of(row: _HasUpdatedAt) -> str:
    """The strong validator: nothing changes a row without moving updated_at."""
    return f'"{row.updated_at.isoformat()}"'


def set_etag(response: Response, row: _HasUpdatedAt) -> None:
    """On detail reads, so a client has something to send back as If-Match."""
    response.headers["ETag"] = etag_of(row)


def require_if_match(request: Request, row: _HasUpdatedAt, current: dict[str, Any]) -> None:
    """Enforce `If-Match` when the caller sent one; be yesterday when not."""
    expected = request.headers.get("if-match")
    if expected is None:
        return
    if expected != etag_of(row):
        raise PreconditionFailedError(current)
