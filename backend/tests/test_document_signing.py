"""Signing a document on somebody else's phone.

The link is the whole authorisation, so most of what is asserted here is what
the link cannot do: outlive its quarter of an hour, be used twice, reach a
second document, or put a signature on a document that never had a line for
one.
"""

import itertools
import struct
import uuid
import zlib
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import MAX_SIGNATURE_BYTES, IssuedDocument
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import User
from app.services import signature_link

pytestmark = pytest.mark.asyncio

BODY = "Hiermit bestätigen wir, dass {{mitglied.name}} Mitglied ist."

#: Counted rather than derived from the name: `hash` is salted per process,
#: so two names could land on one number about once in nine thousand runs.
_numbers = itertools.count(1000)


def a_png(pixels: int = 4) -> bytes:
    """The smallest thing that is honestly a PNG."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(bytes([0]) + bytes([0, 0, 0, 255] * pixels) for _ in range(pixels))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", pixels, pixels, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def data_url(png: bytes) -> str:
    import base64

    return "data:image/png;base64," + base64.b64encode(png).decode()


async def a_member(
    db_session: AsyncSession, tenant: Tenant, user: User, *, number: str = "0042"
) -> Member:
    member = Member(
        tenant_id=tenant.id,
        member_number=number,
        first_name="Erika",
        last_name="Mustermann",
        joined_at=date(2020, 1, 1),
        status="active",
        created_by=user.id,
        updated_by=user.id,
    )
    db_session.add(member)
    await db_session.flush()
    return member


async def a_document(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    tenant: Tenant,
    user: User,
    *,
    signature_mode: str = "line",
    name: str = "Mitgliedsbescheinigung",
) -> dict:
    # A distinct number per document: two members in one club cannot share one.
    member = await a_member(db_session, tenant, user, number=f"{next(_numbers):04d}")
    template = (
        await auth_client.post(
            "/api/v1/documents/templates",
            json={
                "name": name,
                "title": name,
                "body": BODY,
                "signature_mode": signature_mode,
            },
        )
    ).json()["data"]
    response = await auth_client.post(
        f"/api/v1/documents/members/{member.id}/issue", json={"template_id": template["id"]}
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def token_of(url: str) -> str:
    return url.rsplit("/", 1)[-1]


async def test_a_link_lets_a_stranger_sign_that_one_document(
    auth_client: AsyncClient,
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The whole point: the chair signs on their own phone, with no account.

    The signing page shows the document's text — nobody should be asked to
    sign something they are not allowed to read.
    """
    document = await a_document(auth_client, db_session, test_tenant, test_user)

    link = await auth_client.post(f"/api/v1/documents/{document['id']}/signature-link")
    assert link.status_code == 201, link.text
    url = link.json()["data"]["url"]
    assert url.endswith(token_of(url))
    assert link.json()["data"]["qr"], "the phone needs something to scan"

    page = await anon_client.get(f"/sign/{token_of(url)}")
    assert page.status_code == 200
    assert page.json()["data"]["title"] == "Mitgliedsbescheinigung"
    assert "Erika Mustermann" in page.json()["data"]["body"]

    signed = await anon_client.post(
        f"/sign/{token_of(url)}", json={"signature_png": data_url(a_png())}
    )
    assert signed.status_code == 200

    stored = (
        await db_session.execute(
            select(IssuedDocument).where(IssuedDocument.id == uuid.UUID(document["id"]))
        )
    ).scalar_one()
    await db_session.refresh(stored)
    assert stored.signature_png is not None
    assert stored.signed_at is not None


async def test_a_link_works_exactly_once(
    auth_client: AsyncClient,
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A link on a screen is photographed, forwarded, left open. It has to be
    worthless the moment it has done its job."""
    document = await a_document(auth_client, db_session, test_tenant, test_user)
    url = (await auth_client.post(f"/api/v1/documents/{document['id']}/signature-link")).json()[
        "data"
    ]["url"]

    first = await anon_client.post(
        f"/sign/{token_of(url)}", json={"signature_png": data_url(a_png())}
    )
    assert first.status_code == 200

    again = await anon_client.post(
        f"/sign/{token_of(url)}", json={"signature_png": data_url(a_png())}
    )
    assert again.status_code == 404
    assert (await anon_client.get(f"/sign/{token_of(url)}")).status_code == 404


async def test_an_unknown_token_says_nothing(anon_client: AsyncClient) -> None:
    assert (await anon_client.get("/sign/not-a-real-token")).status_code == 404
    assert (
        await anon_client.post("/sign/not-a-real-token", json={"signature_png": data_url(a_png())})
    ).status_code == 404


async def test_a_document_without_a_signature_line_cannot_be_signed(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A machine-made document says it is valid without a signature. Putting
    one on it afterwards would make the page contradict itself."""
    document = await a_document(
        auth_client, db_session, test_tenant, test_user, signature_mode="machine"
    )

    response = await auth_client.post(f"/api/v1/documents/{document['id']}/signature-link")
    assert response.status_code == 422


async def test_a_revoked_document_cannot_be_signed(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    document = await a_document(auth_client, db_session, test_tenant, test_user)
    await auth_client.post(f"/api/v1/documents/{document['id']}/revoke", json={"reason": "Fehler"})

    response = await auth_client.post(f"/api/v1/documents/{document['id']}/signature-link")
    assert response.status_code == 409


async def test_signing_twice_is_refused_even_with_a_fresh_link(
    auth_client: AsyncClient,
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The document is the thing that can only be signed once, not the link."""
    document = await a_document(auth_client, db_session, test_tenant, test_user)
    url = (await auth_client.post(f"/api/v1/documents/{document['id']}/signature-link")).json()[
        "data"
    ]["url"]
    assert (
        await anon_client.post(f"/sign/{token_of(url)}", json={"signature_png": data_url(a_png())})
    ).status_code == 200

    assert (
        await auth_client.post(f"/api/v1/documents/{document['id']}/signature-link")
    ).status_code == 409


async def test_what_is_posted_has_to_be_a_png_of_sane_size(
    auth_client: AsyncClient,
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The endpoint is unauthenticated, so what it accepts is the whole guard:
    a signature is a few strokes, not a photograph."""
    import base64

    document = await a_document(auth_client, db_session, test_tenant, test_user)

    url = (await auth_client.post(f"/api/v1/documents/{document['id']}/signature-link")).json()[
        "data"
    ]["url"]
    not_a_png = base64.b64encode(b"<svg>nope</svg>").decode()
    assert (
        await anon_client.post(f"/sign/{token_of(url)}", json={"signature_png": not_a_png})
    ).status_code == 422

    url = (await auth_client.post(f"/api/v1/documents/{document['id']}/signature-link")).json()[
        "data"
    ]["url"]
    huge = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"x" * MAX_SIGNATURE_BYTES).decode()
    assert (
        await anon_client.post(f"/sign/{token_of(url)}", json={"signature_png": huge})
    ).status_code == 422


async def test_a_token_names_one_document_and_not_the_club(
    auth_client: AsyncClient,
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A link for one certificate must not sign the next one.

    Asserted on the stored target rather than by trying, because there is no
    way to ask for a link that covers two documents — which is the point.
    """
    first = await a_document(auth_client, db_session, test_tenant, test_user, name="Erste")
    second = await a_document(auth_client, db_session, test_tenant, test_user, name="Zweite")

    url = (await auth_client.post(f"/api/v1/documents/{first['id']}/signature-link")).json()[
        "data"
    ]["url"]
    target = await signature_link.peek(token_of(url))

    assert target is not None
    assert str(target.document_id) == first["id"]
    assert str(target.document_id) != second["id"]

    await anon_client.post(f"/sign/{token_of(url)}", json={"signature_png": data_url(a_png())})
    unsigned = (
        await db_session.execute(
            select(IssuedDocument).where(IssuedDocument.id == uuid.UUID(second["id"]))
        )
    ).scalar_one()
    await db_session.refresh(unsigned)
    assert unsigned.signed_at is None


async def test_the_pdf_carries_the_signature_afterwards(
    auth_client: AsyncClient,
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The PDF is re-rendered on every download, so the drawing has to be
    something the document keeps rather than a file that was produced once."""
    document = await a_document(auth_client, db_session, test_tenant, test_user)
    before = await auth_client.get(f"/api/v1/documents/{document['id']}/pdf")

    url = (await auth_client.post(f"/api/v1/documents/{document['id']}/signature-link")).json()[
        "data"
    ]["url"]
    await anon_client.post(f"/sign/{token_of(url)}", json={"signature_png": data_url(a_png(64))})

    after = await auth_client.get(f"/api/v1/documents/{document['id']}/pdf")
    assert after.status_code == 200
    assert after.content.startswith(b"%PDF")
    # The drawing is embedded, so the file cannot be the same one as before.
    assert len(after.content) > len(before.content)


async def test_asking_for_a_link_is_board_work(
    auth_client: AsyncClient,
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    document = await a_document(auth_client, db_session, test_tenant, test_user)
    response = await anon_client.post(f"/api/v1/documents/{document['id']}/signature-link")
    assert response.status_code == 403
