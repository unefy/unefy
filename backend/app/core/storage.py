"""Somewhere to keep bytes.

Until now the backend produced files (certificates, receipts) and never kept
one: everything lived in the database or was rendered on the way out. The
document library needs the other thing — a scanned protocol has to survive a
restart, and a database column is the wrong place for twenty megabytes.

Two rules shape what follows, both from `docs/plans/document-library.md`:

1. **A local volume is the normal case.** `docker compose up` must not require
   an object store for a club to file its statutes. S3 is an option for the
   hosted deployment, not the baseline — hence a narrow protocol with one
   implementation today and room for a second.
2. **The filename is input, never a path.** Callers hand in a key built by
   `build_key`, the display name stays in the database. `../`, colons, emoji
   and 300-character names are therefore a display problem, not a way out of
   the storage root. `_validate_key` refuses anything else outright rather
   than sanitising it, because a sanitiser that gets it wrong writes the file
   anyway.
"""

import hashlib
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import aiofiles
import aiofiles.os

from app.config import get_settings

#: Read and write size. Large enough that a 25 MB upload is a few hundred
#: round trips, small enough that a dozen concurrent ones do not add up to
#: real memory.
CHUNK_SIZE = 64 * 1024

#: Half-written uploads live here until they are complete. The leading dot is
#: load-bearing: `_validate_key` refuses a segment that starts with one, so no
#: key can ever address this directory or anything in it.
TMP_DIRNAME = ".tmp"

#: A key segment: starts alphanumeric, then alphanumerics, dot, dash,
#: underscore. UUIDs pass, `..` does not, and neither does an empty segment,
#: a leading dot, a backslash, or a NUL byte.
_SEGMENT = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\Z")

#: Matches the `storage_key` column, which is the real limit.
MAX_KEY_LENGTH = 512


class StorageError(Exception):
    """Base for everything this module raises."""


class InvalidKeyError(StorageError, ValueError):
    """The key is not a key. Never caused by user input — see `build_key`."""


class ObjectNotFoundError(StorageError):
    """No object under this key. The database row and the blob disagree."""


class ObjectTooLargeError(StorageError):
    """The stream ran past `max_bytes` and was abandoned mid-write."""


@dataclass(frozen=True, slots=True)
class StoredObject:
    """What the caller has to write down after a successful `put`.

    Size and checksum come from the bytes as they went past, not from a header
    the client sent: a `Content-Length` is a claim, and the row would otherwise
    record the claim rather than the file.
    """

    key: str
    byte_size: int
    checksum_sha256: str


def build_key(tenant_id: uuid.UUID) -> str:
    """The only place a storage key is invented.

    `{tenant_id}/{uuid4}` — the club's own drawer, and a name nobody chose.
    Guessing another club's key means guessing a UUID, and reading it still
    means passing the tenant check on the row.
    """
    return f"{tenant_id}/{uuid.uuid4()}"


def _validate_key(key: str) -> str:
    if not key or len(key) > MAX_KEY_LENGTH:
        raise InvalidKeyError(f"key must be 1..{MAX_KEY_LENGTH} characters")
    segments = key.split("/")
    if not all(_SEGMENT.fullmatch(segment) for segment in segments):
        raise InvalidKeyError(f"not a valid storage key: {key!r}")
    return key


class Storage(Protocol):
    """What a backing store has to be able to do. Deliberately four methods."""

    async def put(
        self,
        key: str,
        stream: AsyncIterator[bytes],
        *,
        max_bytes: int | None = None,
    ) -> StoredObject: ...

    def open(self, key: str) -> AsyncIterator[bytes]: ...

    async def delete(self, key: str) -> bool: ...

    async def exists(self, key: str) -> bool: ...


class LocalStorage:
    """Files under a directory. The default, and the only one for now.

    Writes land in a temporary file and are renamed into place, so a connection
    that drops halfway leaves nothing behind that looks like a whole document.
    `os.replace` is atomic within a filesystem, and the temporary directory
    sits under the same root precisely to stay on one.
    """

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def _path_for(self, key: str) -> Path:
        path = self._root / _validate_key(key)
        # Belt and braces. `_validate_key` already makes traversal impossible;
        # this catches the day someone widens the pattern and does not notice
        # what it was holding shut.
        root = self._root.resolve()
        if root not in path.resolve().parents:
            raise InvalidKeyError(f"key escapes the storage root: {key!r}")
        return path

    async def put(
        self,
        key: str,
        stream: AsyncIterator[bytes],
        *,
        max_bytes: int | None = None,
    ) -> StoredObject:
        """Consume the stream, then move it into place under `key`.

        `max_bytes` is the hard stop. The endpoint checks the declared size
        first, which is politeness; this is the check, because a client that
        lies about `Content-Length` would otherwise fill the disk before
        anybody counted.

        An existing object under the same key is replaced.
        """
        target = self._path_for(key)
        tmp_dir = self._root / TMP_DIRNAME
        await aiofiles.os.makedirs(tmp_dir, exist_ok=True)
        tmp = tmp_dir / f"{uuid.uuid4()}.part"

        digest = hashlib.sha256()
        size = 0
        try:
            handle = await aiofiles.open(tmp, "wb")
            try:
                async for chunk in stream:
                    size += len(chunk)
                    if max_bytes is not None and size > max_bytes:
                        raise ObjectTooLargeError(
                            f"upload exceeds {max_bytes} bytes and was abandoned"
                        )
                    digest.update(chunk)
                    await handle.write(chunk)
            finally:
                await handle.close()
            await aiofiles.os.makedirs(target.parent, exist_ok=True)
            await aiofiles.os.replace(tmp, target)
        except BaseException:
            # Includes cancellation: a client that disconnects mid-upload must
            # not leave a `.part` file lying around for the rest of the year.
            await self._discard(tmp)
            raise

        return StoredObject(key=key, byte_size=size, checksum_sha256=digest.hexdigest())

    async def open(self, key: str) -> AsyncIterator[bytes]:
        """Stream the object out in chunks.

        `ObjectNotFoundError` is raised on the first iteration, not on the
        call — an async generator does nothing until it is asked. Callers that
        need to answer 404 before the response starts should ask `exists`.
        """
        path = self._path_for(key)
        try:
            handle = await aiofiles.open(path, "rb")
        except FileNotFoundError as exc:
            raise ObjectNotFoundError(key) from exc
        try:
            while chunk := await handle.read(CHUNK_SIZE):
                yield chunk
        finally:
            await handle.close()

    async def delete(self, key: str) -> bool:
        """Remove the object. False when there was nothing to remove.

        Deleting has to actually delete — a row marked `deleted_at` with the
        bytes still on disk is not an answer to an erasure request.
        """
        try:
            await aiofiles.os.remove(self._path_for(key))
        except FileNotFoundError:
            return False
        return True

    async def exists(self, key: str) -> bool:
        return await aiofiles.os.path.isfile(self._path_for(key))

    @staticmethod
    async def _discard(path: Path) -> None:
        with suppress(FileNotFoundError):
            await aiofiles.os.remove(path)


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.STORAGE_BACKEND != "local":
        # Unreachable through Settings, which refuses the value at startup.
        # Kept so that adding the setting is not enough to appear to add the
        # backend.
        raise NotImplementedError(f"storage backend {settings.STORAGE_BACKEND!r} is not built yet")
    return LocalStorage(settings.STORAGE_PATH)
