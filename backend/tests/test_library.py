"""The club's filing cabinet, end to end.

The tests that carry this module are the ones the plan named: another club
never sees a file, a member never sees a committee file, a ZIP called `.pdf`
is refused, a filename with `../` still lands under the club's own key, an
upload over the quota is refused *before* anything is written, and a delete
takes the bytes with it. The rest — folders, versions, headers — is here
because a filing cabinet with a broken drawer is not a filing cabinet.
"""

import io
import json
import uuid
import zipfile
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.storage import LocalStorage, get_storage
from app.models import LibraryDocument, Tenant
from app.models.audit import TenantAuditLog
from app.models.user import TenantMembership, User

BASE = "/api/v1/library"

PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"0" * 64
TEXT = "Tagesordnung\nTOP 1: Begrüßung\n".encode()
ICS = b"BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n"


def _zip(entries: list[tuple[str, bytes]], *, first_stored: bool = False) -> bytes:
    """A real ZIP file, so the detector sees a real local file header."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, (name, content) in enumerate(entries):
            compress = zipfile.ZIP_STORED if first_stored and index == 0 else zipfile.ZIP_DEFLATED
            archive.writestr(name, content, compress_type=compress)
    return buffer.getvalue()


ZIP = _zip([("readme.txt", b"just an archive")])
DOCX = _zip(
    [
        ("[Content_Types].xml", b"<Types/>"),
        ("word/document.xml", b"<document/>"),
    ]
)
ODT = _zip(
    [
        ("mimetype", b"application/vnd.oasis.opendocument.text"),
        ("content.xml", b"<office/>"),
    ],
    first_stored=True,
)


# --- Fixtures ---


@pytest.fixture
def storage(tmp_path: Path) -> "CountingStorage":
    """A storage root of this test's own, wired into the app."""
    from app.main import app

    store = CountingStorage(tmp_path / "storage")
    app.dependency_overrides[get_storage] = lambda: store
    return store


class CountingStorage(LocalStorage):
    """A real local storage that also remembers how often it was written to.

    The count is what makes "refused before anything was written" checkable.
    Looking at the directory afterwards cannot prove it: `put` cleans up after
    itself, so a refusal that happened *during* the write leaves the same empty
    directory as one that happened before it.
    """

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.writes = 0

    async def put(self, key: str, stream: Any, *, max_bytes: int | None = None) -> Any:
        self.writes += 1
        return await super().put(key, stream, max_bytes=max_bytes)


def _stored_files(storage: CountingStorage) -> list[Path]:
    if not storage.root.exists():
        return []
    return [path for path in storage.root.rglob("*") if path.is_file()]


@pytest.fixture
def limits() -> Any:
    """Override the size and quota settings for one test."""
    from app.main import app

    def apply(*, max_upload: int, quota: int) -> None:
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            DEBUG=True,
            MAX_UPLOAD_BYTES=max_upload,
            TENANT_STORAGE_QUOTA_BYTES=quota,
        )
        app.dependency_overrides[get_settings] = lambda: settings

    return apply


async def _client_for(
    db_session: AsyncSession,
    fake_redis: Any,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
) -> AsyncGenerator[AsyncClient]:
    import app.redis as redis_module
    from app.database import get_db_session
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    original_redis = redis_module._redis_client
    redis_module._redis_client = fake_redis

    token = uuid.uuid4().hex
    await fake_redis.set(
        f"session:{token}",
        json.dumps({"user_id": str(user_id), "tenant_id": str(tenant_id), "role": role}),
        ex=3600,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": token},
    ) as ac:
        yield ac

    redis_module._redis_client = original_redis


@pytest.fixture
async def member_client(
    db_session: AsyncSession, fake_redis: Any, test_tenant: Tenant
) -> AsyncGenerator[AsyncClient]:
    """An ordinary member of the same club."""
    user = User(id=uuid.uuid4(), email="mitglied@example.com", name="Mitglied")
    db_session.add(user)
    db_session.add(
        TenantMembership(
            id=uuid.uuid4(),
            user_id=user.id,
            tenant_id=test_tenant.id,
            role="member",
            is_active=True,
        )
    )
    await db_session.flush()
    async for client in _client_for(
        db_session, fake_redis, user_id=user.id, tenant_id=test_tenant.id, role="member"
    ):
        yield client


@pytest.fixture
async def other_club_client(
    db_session: AsyncSession, fake_redis: Any
) -> AsyncGenerator[AsyncClient]:
    """The owner of a different club entirely."""
    tenant = Tenant(id=uuid.uuid4(), name="Nachbarverein", slug="nachbarverein")
    user = User(id=uuid.uuid4(), email="vorstand@nachbarverein.example", name="Nachbar")
    db_session.add_all([tenant, user])
    db_session.add(
        TenantMembership(
            id=uuid.uuid4(),
            user_id=user.id,
            tenant_id=tenant.id,
            role="owner",
            is_active=True,
        )
    )
    await db_session.flush()
    async for client in _client_for(
        db_session, fake_redis, user_id=user.id, tenant_id=tenant.id, role="owner"
    ):
        yield client


async def upload(
    client: AsyncClient,
    *,
    content: bytes = PDF,
    filename: str = "satzung.pdf",
    title: str = "Satzung",
    **form: Any,
) -> Any:
    return await client.post(
        f"{BASE}/documents",
        files={"file": (filename, content, "application/octet-stream")},
        data={"title": title, **{k: str(v) for k, v in form.items() if v is not None}},
    )


async def create_folder(client: AsyncClient, name: str, parent_id: str | None = None) -> Any:
    payload: dict[str, Any] = {"name": name}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    return await client.post(f"{BASE}/folders", json=payload)


# --- Filing something at all ---


async def test_a_document_can_be_filed_and_read_back(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    response = await upload(auth_client, title="Satzung 2026", description="Fassung der MV")

    assert response.status_code == 201, response.text
    document = response.json()["data"]
    assert document["title"] == "Satzung 2026"
    assert document["content_type"] == "application/pdf"
    assert document["byte_size"] == len(PDF)
    assert document["visibility"] == "board"
    # The key never travels: nothing outside the backend has business knowing
    # where the bytes are.
    assert "storage_key" not in document

    content = await auth_client.get(f"{BASE}/documents/{document['id']}/content")
    assert content.status_code == 200
    assert content.content == PDF


async def test_the_list_shows_what_was_filed(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    await upload(auth_client, title="Satzung")
    await upload(auth_client, title="Protokoll", filename="protokoll.pdf")

    response = await auth_client.get(f"{BASE}/documents")

    assert response.status_code == 200
    body = response.json()
    assert {d["title"] for d in body["data"]} == {"Satzung", "Protokoll"}
    assert body["meta"]["total"] == 2


async def test_the_search_looks_in_every_drawer(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    folder = (await create_folder(auth_client, "Protokolle")).json()["data"]
    await upload(auth_client, title="Protokoll 2026", folder_id=folder["id"])

    in_root = await auth_client.get(f"{BASE}/documents")
    found = await auth_client.get(f"{BASE}/documents", params={"search": "protokoll"})

    assert in_root.json()["data"] == [], "a filed document must not also sit in the root"
    assert [d["title"] for d in found.json()["data"]] == ["Protokoll 2026"]


async def test_the_usage_endpoint_counts_what_is_stored(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    await upload(auth_client)

    usage = (await auth_client.get(f"{BASE}/usage")).json()["data"]

    assert usage["used_bytes"] == len(PDF)
    assert usage["quota_bytes"] > usage["used_bytes"]
    assert usage["max_upload_bytes"] > 0


# --- Tenant isolation: the test that must not be missing ---


async def test_another_club_sees_nothing_of_this_one(
    auth_client: AsyncClient, other_club_client: AsyncClient, storage: CountingStorage
) -> None:
    document = (await upload(auth_client, visibility="members")).json()["data"]

    listing = await other_club_client.get(f"{BASE}/documents")
    by_id = await other_club_client.get(f"{BASE}/documents/{document['id']}")
    content = await other_club_client.get(f"{BASE}/documents/{document['id']}/content")
    patch = await other_club_client.patch(
        f"{BASE}/documents/{document['id']}", json={"title": "Übernommen"}
    )
    delete = await other_club_client.delete(f"{BASE}/documents/{document['id']}")

    assert listing.json()["data"] == []
    assert by_id.status_code == 404
    assert content.status_code == 404
    assert patch.status_code == 404
    assert delete.status_code == 404


async def test_another_clubs_folder_is_not_a_place_to_file_into(
    auth_client: AsyncClient, other_club_client: AsyncClient, storage: CountingStorage
) -> None:
    folder = (await create_folder(auth_client, "Protokolle")).json()["data"]

    response = await upload(other_club_client, folder_id=folder["id"])

    assert response.status_code == 404


# --- Visibility ---


async def test_a_member_does_not_see_committee_documents(
    auth_client: AsyncClient, member_client: AsyncClient, storage: CountingStorage
) -> None:
    board = (await upload(auth_client, title="Vorstandsprotokoll")).json()["data"]
    shared = (await upload(auth_client, title="Hausordnung", visibility="members")).json()["data"]

    listing = await member_client.get(f"{BASE}/documents")
    hidden = await member_client.get(f"{BASE}/documents/{board['id']}")
    hidden_content = await member_client.get(f"{BASE}/documents/{board['id']}/content")
    visible = await member_client.get(f"{BASE}/documents/{shared['id']}/content")

    assert [d["title"] for d in listing.json()["data"]] == ["Hausordnung"]
    assert hidden.status_code == 404
    assert hidden_content.status_code == 404
    assert visible.status_code == 200
    assert visible.content == PDF


async def test_a_member_may_not_file_rename_or_remove_anything(
    auth_client: AsyncClient, member_client: AsyncClient, storage: CountingStorage
) -> None:
    document = (await upload(auth_client, title="Hausordnung", visibility="members")).json()["data"]

    assert (await upload(member_client)).status_code == 403
    assert (await create_folder(member_client, "Eigenes")).status_code == 403
    assert (
        await member_client.patch(f"{BASE}/documents/{document['id']}", json={"title": "X"})
    ).status_code == 403
    assert (await member_client.delete(f"{BASE}/documents/{document['id']}")).status_code == 403


async def test_making_a_document_visible_is_recorded_as_such(
    auth_client: AsyncClient, db_session: AsyncSession, storage: CountingStorage
) -> None:
    """The one edit with a security meaning gets its own name in the log."""
    document = (await upload(auth_client)).json()["data"]

    response = await auth_client.patch(
        f"{BASE}/documents/{document['id']}", json={"visibility": "members"}
    )

    assert response.status_code == 200
    assert response.json()["data"]["visibility"] == "members"
    actions = (
        (
            await db_session.execute(
                select(TenantAuditLog.action).where(
                    TenantAuditLog.target_id == uuid.UUID(document["id"])
                )
            )
        )
        .scalars()
        .all()
    )
    assert "library_document.visibility_changed" in actions
    assert "library_document.uploaded" in actions


# --- What the bytes actually are ---


async def test_an_archive_named_pdf_is_refused(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    """The extension is a claim; the first bytes are not."""
    response = await upload(auth_client, content=ZIP, filename="protokoll.pdf")

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    assert _stored_files(storage) == [], "a refused upload was written anyway"


@pytest.mark.parametrize(
    ("content", "filename", "expected"),
    [
        (PDF, "satzung.pdf", "application/pdf"),
        (PNG, "wappen.png", "image/png"),
        (
            DOCX,
            "vorlage.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (ODT, "vorlage.odt", "application/vnd.oasis.opendocument.text"),
        (TEXT, "notiz.txt", "text/plain"),
        (TEXT, "mitglieder.csv", "text/csv"),
        (ICS, "termine.ics", "text/calendar"),
    ],
)
async def test_the_accepted_types_are_accepted(
    auth_client: AsyncClient,
    storage: CountingStorage,
    content: bytes,
    filename: str,
    expected: str,
) -> None:
    response = await upload(auth_client, content=content, filename=filename)

    assert response.status_code == 201, response.text
    assert response.json()["data"]["content_type"] == expected


async def test_a_pdf_wearing_a_png_name_is_stored_as_a_pdf(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    response = await upload(auth_client, content=PDF, filename="wappen.png")

    assert response.json()["data"]["content_type"] == "application/pdf"


async def test_an_executable_is_not_a_document(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    response = await upload(
        auth_client, content=b"\x7fELF\x02\x01\x01" + b"\x00" * 40, filename="tool.txt"
    )

    assert response.status_code == 415


async def test_an_empty_file_is_refused(auth_client: AsyncClient, storage: CountingStorage) -> None:
    response = await upload(auth_client, content=b"", filename="leer.pdf")

    assert response.status_code == 415


# --- The filename is a name, not a path ---


async def test_a_filename_pretending_to_be_a_path_lands_under_the_club(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    storage: CountingStorage,
    test_tenant: Tenant,
) -> None:
    response = await upload(auth_client, filename="../../etc/passwd.pdf")

    assert response.status_code == 201
    document_id = uuid.UUID(response.json()["data"]["id"])
    row = (
        await db_session.execute(select(LibraryDocument).where(LibraryDocument.id == document_id))
    ).scalar_one()
    assert row.storage_key.startswith(f"{test_tenant.id}/")
    assert row.original_filename == "passwd.pdf", "the directories are not part of a name"
    assert [p.parent.name for p in _stored_files(storage)] == [str(test_tenant.id)]


async def test_a_filename_cannot_break_the_download_header(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    response = await upload(auth_client, filename='sat"zung\r\n.pdf')

    assert response.status_code == 201
    assert '"' not in response.json()["data"]["original_filename"]
    assert "\n" not in response.json()["data"]["original_filename"]


# --- Size and quota ---


async def test_a_file_over_the_limit_is_refused_before_it_is_written(
    auth_client: AsyncClient, storage: CountingStorage, limits: Any
) -> None:
    limits(max_upload=len(PDF) - 1, quota=10_000_000)

    response = await upload(auth_client)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "UPLOAD_TOO_LARGE"
    assert storage.writes == 0, "the file was written and only then measured"
    assert _stored_files(storage) == []


async def test_the_quota_is_checked_before_a_single_byte_is_stored(
    auth_client: AsyncClient, db_session: AsyncSession, storage: CountingStorage, limits: Any
) -> None:
    """An "out of space" answer paid for with the last of the space is no answer."""
    limits(max_upload=1_000_000, quota=len(PDF) + 10)
    first = await upload(auth_client, title="Erste")
    assert first.status_code == 201
    storage.writes = 0

    second = await upload(auth_client, title="Zweite", filename="zweite.pdf")

    assert second.status_code == 413
    assert second.json()["error"]["code"] == "STORAGE_QUOTA_EXCEEDED"
    assert storage.writes == 0, "the club paid for the answer with the last of its space"
    assert len(_stored_files(storage)) == 1, "the refused upload left bytes behind"
    rows = (await db_session.execute(select(LibraryDocument))).scalars().all()
    assert [r.title for r in rows] == ["Erste"]


async def test_a_client_that_understates_its_size_is_still_stopped(
    auth_client: AsyncClient, storage: CountingStorage, limits: Any
) -> None:
    """The declared size is politeness; the counted bytes are the limit.

    Sent as a raw multipart body so no `Content-Length` for the part is
    declared at all — which is exactly the shape a lying client would use.
    """
    limits(max_upload=len(PDF) - 1, quota=10_000_000)
    boundary = "----unefytest"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="title"\r\n\r\nSatzung\r\n'
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="satzung.pdf"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + PDF
        + f"\r\n--{boundary}--\r\n".encode()
    )

    response = await auth_client.post(
        f"{BASE}/documents",
        content=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    assert response.status_code == 413
    assert _stored_files(storage) == [], "an oversized upload survived the write"


async def test_a_declared_body_over_the_limit_never_reaches_the_endpoint() -> None:
    """Starlette spools the body before the handler runs, so the check is here.

    Without it a 5 GB "upload" to a 25 MB library is written to /tmp in full
    and only then declined.
    """
    from starlette.requests import Request

    from app.api.middleware.body_limit import BodySizeLimitMiddleware

    middleware = BodySizeLimitMiddleware(app=None, max_bytes=1000)
    reached = False

    async def call_next(_request: Request) -> Any:  # pragma: no cover - must not run
        nonlocal reached
        reached = True
        raise AssertionError("the endpoint was reached")

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/library/documents",
            "headers": [(b"content-length", b"999999999")],
            "query_string": b"",
        }
    )
    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 413
    assert reached is False


# --- Deleting has to delete ---


async def test_deleting_takes_the_bytes_with_it(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    document = (await upload(auth_client)).json()["data"]
    assert len(_stored_files(storage)) == 1

    response = await auth_client.delete(f"{BASE}/documents/{document['id']}")

    assert response.status_code == 204
    assert _stored_files(storage) == [], "the row went and the file stayed"
    assert (await auth_client.get(f"{BASE}/documents/{document['id']}")).status_code == 404
    assert (await auth_client.get(f"{BASE}/documents")).json()["data"] == []


async def test_a_deleted_document_stops_counting_against_the_quota(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    document = (await upload(auth_client)).json()["data"]
    await auth_client.delete(f"{BASE}/documents/{document['id']}")

    usage = (await auth_client.get(f"{BASE}/usage")).json()["data"]

    assert usage["used_bytes"] == 0


# --- Folders ---


async def test_folders_nest(auth_client: AsyncClient, storage: CountingStorage) -> None:
    minutes = (await create_folder(auth_client, "Protokolle")).json()["data"]
    year = (await create_folder(auth_client, "2026", minutes["id"])).json()["data"]

    folders = (await auth_client.get(f"{BASE}/folders")).json()["data"]

    assert {f["name"] for f in folders} == {"Protokolle", "2026"}
    assert year["parent_id"] == minutes["id"]


async def test_two_folders_of_one_name_in_one_place_are_refused(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    """Including at the root, where SQL would otherwise treat every NULL parent
    as a different place and allow the duplicate."""
    assert (await create_folder(auth_client, "Protokolle")).status_code == 201

    assert (await create_folder(auth_client, "Protokolle")).status_code == 409


async def test_the_same_name_in_two_different_drawers_is_fine(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    minutes = (await create_folder(auth_client, "Protokolle")).json()["data"]
    finance = (await create_folder(auth_client, "Finanzen")).json()["data"]

    first = await create_folder(auth_client, "2026", minutes["id"])
    second = await create_folder(auth_client, "2026", finance["id"])

    assert first.status_code == 201
    assert second.status_code == 201


async def test_a_folder_cannot_be_moved_into_itself(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    folder = (await create_folder(auth_client, "Protokolle")).json()["data"]

    response = await auth_client.patch(
        f"{BASE}/folders/{folder['id']}", json={"parent_id": folder["id"]}
    )

    assert response.status_code == 422


async def test_a_folder_cannot_be_moved_under_its_own_child(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    """The move the database cannot see: the branch would leave the tree and
    every row in it would stop being reachable from the root."""
    top = (await create_folder(auth_client, "Protokolle")).json()["data"]
    middle = (await create_folder(auth_client, "2026", top["id"])).json()["data"]
    bottom = (await create_folder(auth_client, "Q1", middle["id"])).json()["data"]

    response = await auth_client.patch(
        f"{BASE}/folders/{top['id']}", json={"parent_id": bottom["id"]}
    )

    assert response.status_code == 422
    folders = (await auth_client.get(f"{BASE}/folders")).json()["data"]
    assert {f["id"]: f["parent_id"] for f in folders}[top["id"]] is None


async def test_a_folder_can_be_renamed_and_moved(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    top = (await create_folder(auth_client, "Protokolle")).json()["data"]
    other = (await create_folder(auth_client, "Archiv")).json()["data"]

    response = await auth_client.patch(
        f"{BASE}/folders/{top['id']}", json={"name": "Sitzungen", "parent_id": other["id"]}
    )

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Sitzungen"
    assert response.json()["data"]["parent_id"] == other["id"]


async def test_a_folder_with_something_in_it_is_not_deleted(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    """A delete that quietly takes twenty documents is not a delete."""
    folder = (await create_folder(auth_client, "Protokolle")).json()["data"]
    child = (await create_folder(auth_client, "2026", folder["id"])).json()["data"]

    with_child = await auth_client.delete(f"{BASE}/folders/{folder['id']}")
    assert with_child.status_code == 409

    await auth_client.delete(f"{BASE}/folders/{child['id']}")
    await upload(auth_client, folder_id=folder["id"])
    with_document = await auth_client.delete(f"{BASE}/folders/{folder['id']}")

    assert with_document.status_code == 409


async def test_an_empty_folder_is_deleted(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    folder = (await create_folder(auth_client, "Leer")).json()["data"]

    response = await auth_client.delete(f"{BASE}/folders/{folder['id']}")

    assert response.status_code == 204
    assert (await auth_client.get(f"{BASE}/folders")).json()["data"] == []


async def test_a_folder_hides_no_documents_from_the_emptiness_check(
    auth_client: AsyncClient, member_client: AsyncClient, storage: CountingStorage
) -> None:
    """A drawer holding a committee file is not empty, whoever is asking."""
    folder = (await create_folder(auth_client, "Vorstand")).json()["data"]
    await upload(auth_client, folder_id=folder["id"], visibility="board")

    response = await auth_client.delete(f"{BASE}/folders/{folder['id']}")

    assert response.status_code == 409


# --- Versions ---


async def test_a_new_version_replaces_the_old_one_in_the_list(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    first = (await upload(auth_client, title="Satzung")).json()["data"]

    second = await auth_client.post(
        f"{BASE}/documents/{first['id']}/version",
        files={"file": ("satzung-2026.pdf", PDF + b"neu", "application/octet-stream")},
    )

    assert second.status_code == 201, second.text
    new_version = second.json()["data"]
    assert new_version["replaces_id"] == first["id"]
    assert new_version["title"] == "Satzung", "the title carries over"

    listing = (await auth_client.get(f"{BASE}/documents")).json()["data"]
    assert [d["id"] for d in listing] == [new_version["id"]]

    both = (await auth_client.get(f"{BASE}/documents")).json()
    assert both["meta"]["total"] == 1


async def test_the_old_version_is_still_there_to_be_asked_for(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    """ "Which statutes applied in 2024" is the whole point of keeping them."""
    first = (await upload(auth_client, title="Satzung")).json()["data"]
    second = (
        await auth_client.post(
            f"{BASE}/documents/{first['id']}/version",
            files={"file": ("satzung-2026.pdf", PDF + b"neu", "application/octet-stream")},
        )
    ).json()["data"]

    versions = (await auth_client.get(f"{BASE}/documents/{second['id']}/versions")).json()["data"]
    old_content = await auth_client.get(f"{BASE}/documents/{first['id']}/content")

    assert [v["id"] for v in versions] == [second["id"], first["id"]]
    assert old_content.content == PDF
    assert versions[1]["superseded_at"] is not None


async def test_a_superseded_version_does_not_get_its_own_successor(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    """Two current successors of one document is a fork, and a filing cabinet
    has no way to show one."""
    first = (await upload(auth_client, title="Satzung")).json()["data"]
    await auth_client.post(
        f"{BASE}/documents/{first['id']}/version",
        files={"file": ("v2.pdf", PDF + b"2", "application/octet-stream")},
    )

    third = await auth_client.post(
        f"{BASE}/documents/{first['id']}/version",
        files={"file": ("v3.pdf", PDF + b"3", "application/octet-stream")},
    )

    assert third.status_code == 409


async def test_superseded_versions_can_be_listed_on_request(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    first = (await upload(auth_client, title="Satzung")).json()["data"]
    await auth_client.post(
        f"{BASE}/documents/{first['id']}/version",
        files={"file": ("v2.pdf", PDF + b"2", "application/octet-stream")},
    )

    listing = await auth_client.get(f"{BASE}/documents", params={"include_superseded": "true"})

    assert listing.json()["meta"]["total"] == 2


async def test_a_members_document_keeps_its_visibility_across_versions(
    auth_client: AsyncClient, member_client: AsyncClient, storage: CountingStorage
) -> None:
    """Re-deciding on every upload is how the second copy ends up hidden."""
    first = (await upload(auth_client, visibility="members")).json()["data"]

    second = await auth_client.post(
        f"{BASE}/documents/{first['id']}/version",
        files={"file": ("v2.pdf", PDF + b"2", "application/octet-stream")},
    )

    assert second.json()["data"]["visibility"] == "members"
    assert (await member_client.get(f"{BASE}/documents")).json()["meta"]["total"] == 1


# --- Delivering the bytes ---


async def test_a_pdf_opens_and_everything_else_downloads(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    pdf = (await upload(auth_client)).json()["data"]
    docx = (
        await upload(auth_client, content=DOCX, filename="vorlage.docx", title="Vorlage")
    ).json()["data"]

    pdf_response = await auth_client.get(f"{BASE}/documents/{pdf['id']}/content")
    docx_response = await auth_client.get(f"{BASE}/documents/{docx['id']}/content")

    assert pdf_response.headers["content-disposition"].startswith("inline")
    assert docx_response.headers["content-disposition"].startswith("attachment")


async def test_the_download_forbids_guessing_at_the_type(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    """`nosniff` plus the detected type is what stops an upload being run as
    something else."""
    document = (await upload(auth_client)).json()["data"]

    response = await auth_client.get(f"{BASE}/documents/{document['id']}/content")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"].startswith("application/pdf")


async def test_an_umlaut_survives_the_download_header(
    auth_client: AsyncClient, storage: CountingStorage
) -> None:
    document = (await upload(auth_client, filename="Mitgliederjubiläum.pdf")).json()["data"]

    response = await auth_client.get(f"{BASE}/documents/{document['id']}/content")

    disposition = response.headers["content-disposition"]
    assert "filename*=UTF-8''Mitgliederjubil%C3%A4um.pdf" in disposition
    assert disposition.isascii(), "a raw umlaut here is read differently by every client"


# --- Housekeeping ---


async def test_the_upload_is_written_to_the_audit_log(
    auth_client: AsyncClient, db_session: AsyncSession, storage: CountingStorage
) -> None:
    document = (await upload(auth_client)).json()["data"]

    entry = (
        await db_session.execute(
            select(TenantAuditLog)
            .where(TenantAuditLog.target_id == uuid.UUID(document["id"]))
            .where(TenantAuditLog.action == "library_document.uploaded")
        )
    ).scalar_one()

    assert entry.changes is not None
    assert entry.changes["filename"] == "satzung.pdf"


async def test_deleting_is_written_to_the_audit_log(
    auth_client: AsyncClient, db_session: AsyncSession, storage: CountingStorage
) -> None:
    document = (await upload(auth_client)).json()["data"]

    await auth_client.delete(f"{BASE}/documents/{document['id']}")

    actions = (
        (
            await db_session.execute(
                select(TenantAuditLog.action).where(
                    TenantAuditLog.target_id == uuid.UUID(document["id"])
                )
            )
        )
        .scalars()
        .all()
    )
    assert "library_document.deleted" in actions


async def test_signing_in_is_required(anon_client: AsyncClient, storage: CountingStorage) -> None:
    """No public buckets, no guessable URLs — including the listing."""
    assert (await anon_client.get(f"{BASE}/documents")).status_code == 403
    assert (await anon_client.get(f"{BASE}/folders")).status_code == 403
    assert (await anon_client.get(f"{BASE}/documents/{uuid.uuid4()}/content")).status_code == 403
