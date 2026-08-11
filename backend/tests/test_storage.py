"""Keeping bytes, and the four ways that goes wrong.

No database here — this is the layer under everything the document library
will do, and it has to hold on its own: a key that is a path, an upload that
stops halfway, a limit that is only checked after the disk is full, a delete
that leaves the file. Each of those is a test below.
"""

import hashlib
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.config import Settings
from app.core.storage import (
    CHUNK_SIZE,
    TMP_DIRNAME,
    InvalidKeyError,
    LocalStorage,
    ObjectNotFoundError,
    ObjectTooLargeError,
    build_key,
)

PDF = b"%PDF-1.7\nthe minutes of the general meeting\n"


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


async def _stream_that_fails(chunk: bytes) -> AsyncIterator[bytes]:
    yield chunk
    raise ConnectionResetError("the phone went into a lift")


async def _collect(chunks: AsyncIterator[bytes]) -> bytes:
    return b"".join([chunk async for chunk in chunks])


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path / "storage")


@pytest.fixture
def key() -> str:
    return build_key(uuid.uuid4())


def _leftovers(storage: LocalStorage) -> list[Path]:
    tmp_dir = storage.root / TMP_DIRNAME
    return sorted(tmp_dir.iterdir()) if tmp_dir.is_dir() else []


# --- The ordinary case ---


async def test_a_document_survives_the_round_trip(storage: LocalStorage, key: str) -> None:
    stored = await storage.put(key, _stream(PDF))

    assert stored.key == key
    assert stored.byte_size == len(PDF)
    assert stored.checksum_sha256 == hashlib.sha256(PDF).hexdigest()
    assert await _collect(storage.open(key)) == PDF
    assert await storage.exists(key)


async def test_the_size_and_checksum_describe_the_bytes_that_arrived(
    storage: LocalStorage, key: str
) -> None:
    """Not the header the client sent — that is a claim, and claims can lie."""
    parts = [b"a" * 1000, b"b" * 1000, b"c" * 7]

    stored = await storage.put(key, _stream(*parts))

    assert stored.byte_size == 2007
    assert stored.checksum_sha256 == hashlib.sha256(b"".join(parts)).hexdigest()


async def test_a_large_document_comes_back_in_pieces(storage: LocalStorage, key: str) -> None:
    """A scan is read in chunks, never held whole in memory."""
    content = bytes(range(256)) * 2000  # 512 KB, eight chunks
    await storage.put(key, _stream(content))

    pieces = [chunk async for chunk in storage.open(key)]

    assert len(pieces) > 1
    assert all(len(piece) <= CHUNK_SIZE for piece in pieces)
    assert b"".join(pieces) == content


async def test_the_directory_is_created_on_first_use(tmp_path: Path, key: str) -> None:
    """A fresh install has no storage directory, and must not need one made."""
    storage = LocalStorage(tmp_path / "does-not-exist-yet" / "storage")

    await storage.put(key, _stream(PDF))

    assert await _collect(storage.open(key)) == PDF


async def test_a_new_version_replaces_the_old_bytes(storage: LocalStorage, key: str) -> None:
    await storage.put(key, _stream(b"first draft"))
    await storage.put(key, _stream(b"as adopted"))

    assert await _collect(storage.open(key)) == b"as adopted"


# --- The key is not a path ---


async def test_the_key_names_the_club_and_then_nothing_anyone_chose() -> None:
    tenant_id = uuid.uuid4()

    key = build_key(tenant_id)

    club, _, name = key.partition("/")
    assert club == str(tenant_id)
    assert uuid.UUID(name)  # a name nobody picked, so nobody can guess it


@pytest.mark.parametrize(
    "bad_key",
    [
        "../../etc/passwd",
        "club/../../etc/passwd",
        "/etc/passwd",
        "club//file",
        "club/",
        "",
        ".",
        "..",
        f"{TMP_DIRNAME}/half-an-upload.part",
        "club/.hidden",
        "club\\file",
        "club/file\x00.pdf",
        "club/Satzung 2026.pdf",
        "a" * 513,
    ],
)
async def test_a_key_that_is_really_a_path_is_refused(storage: LocalStorage, bad_key: str) -> None:
    """Refused, not sanitised: a sanitiser that gets it wrong writes anyway."""
    with pytest.raises(InvalidKeyError):
        await storage.put(bad_key, _stream(PDF))
    with pytest.raises(InvalidKeyError):
        await storage.delete(bad_key)
    with pytest.raises(InvalidKeyError):
        await storage.exists(bad_key)
    with pytest.raises(InvalidKeyError):
        await _collect(storage.open(bad_key))


async def test_nothing_is_written_outside_the_storage_root(tmp_path: Path) -> None:
    """The test the guard exists for: `../` must not reach the parent."""
    storage = LocalStorage(tmp_path / "storage")

    with pytest.raises(InvalidKeyError):
        await storage.put("../escaped.pdf", _stream(PDF))

    assert list(tmp_path.iterdir()) == [], "a rejected key created something"


async def test_the_temp_directory_is_not_addressable(storage: LocalStorage, key: str) -> None:
    """Half-written uploads live under a name no key can spell."""
    await storage.put(key, _stream(PDF))

    with pytest.raises(InvalidKeyError):
        await storage.exists(f"{TMP_DIRNAME}/{uuid.uuid4()}.part")


# --- Uploads that do not finish ---


async def test_an_upload_that_breaks_off_leaves_nothing_visible(
    storage: LocalStorage, key: str
) -> None:
    """Half a file that looks like a whole one is worse than no file."""
    with pytest.raises(ConnectionResetError):
        await storage.put(key, _stream_that_fails(b"%PDF-1.7 the first page"))

    assert not await storage.exists(key)
    assert _leftovers(storage) == [], "a .part file survived the failed upload"


async def test_a_failed_new_version_leaves_the_old_one_readable(
    storage: LocalStorage, key: str
) -> None:
    """Uploading a replacement is not a chance to lose what is already filed."""
    await storage.put(key, _stream(b"the statutes as adopted"))

    with pytest.raises(ConnectionResetError):
        await storage.put(key, _stream_that_fails(b"the amended"))

    assert await _collect(storage.open(key)) == b"the statutes as adopted"


async def test_an_upload_over_the_limit_is_stopped_mid_stream(
    storage: LocalStorage, key: str
) -> None:
    """The limit is enforced against the bytes, not against a declared size.

    A client that understates `Content-Length` would otherwise fill the disk
    and only then be counted.
    """
    with pytest.raises(ObjectTooLargeError):
        await storage.put(key, _stream(b"x" * 400, b"x" * 400), max_bytes=500)

    assert not await storage.exists(key)
    assert _leftovers(storage) == []


async def test_an_upload_exactly_on_the_limit_is_kept(storage: LocalStorage, key: str) -> None:
    stored = await storage.put(key, _stream(b"x" * 500), max_bytes=500)

    assert stored.byte_size == 500


# --- Deleting has to delete ---


async def test_delete_removes_the_bytes(storage: LocalStorage, key: str) -> None:
    """An erasure request is not answered by a flag on a row."""
    await storage.put(key, _stream(PDF))

    assert await storage.delete(key) is True

    assert not await storage.exists(key)
    assert not any(p.is_file() for p in storage.root.rglob("*"))


async def test_deleting_twice_is_not_an_error(storage: LocalStorage, key: str) -> None:
    """A retried delete must not fail the request that is cleaning up."""
    await storage.put(key, _stream(PDF))
    await storage.delete(key)

    assert await storage.delete(key) is False


async def test_reading_a_key_that_is_gone_says_so(storage: LocalStorage, key: str) -> None:
    """The row and the blob can disagree; the caller has to be able to tell."""
    with pytest.raises(ObjectNotFoundError):
        await _collect(storage.open(key))

    assert not await storage.exists(key)


# --- Configuration ---


def test_the_default_backend_needs_no_object_store() -> None:
    """`docker compose up` must file a document without an S3 account."""
    settings = Settings(_env_file=None, DEBUG=True)

    assert settings.STORAGE_BACKEND == "local"
    assert settings.MAX_UPLOAD_BYTES == 25 * 1024 * 1024
    assert settings.TENANT_STORAGE_QUOTA_BYTES == 1024 * 1024 * 1024


def test_asking_for_s3_today_is_refused_at_startup() -> None:
    """Booting would mean a club's documents in a container that gets replaced."""
    with pytest.raises(ValueError, match="is not implemented yet"):
        Settings(_env_file=None, DEBUG=True, STORAGE_BACKEND="s3")
