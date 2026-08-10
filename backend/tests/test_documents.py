"""Templates, issuing, and what the two must not let slip."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentTemplate, IssuedDocument
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import User
from app.services import document_variables as variables

pytestmark = pytest.mark.asyncio

BODY = (
    "Hiermit bestätigen wir, dass {{mitglied.name}} "
    "(Mitgliedsnummer {{mitglied.nummer}}) seit {{mitglied.eintritt}} "
    "Mitglied im {{verein.name}} ist.\n\n{{datum}}"
)


def template_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Mitgliedsbescheinigung",
        "title": "Mitgliedsbescheinigung",
        "body": BODY,
    }
    payload.update(overrides)
    return payload


async def a_member(db_session: AsyncSession, tenant: Tenant, user: User, **kw: object) -> Member:
    member = Member(
        tenant_id=tenant.id,
        member_number=str(kw.pop("member_number", "0042")),
        first_name=str(kw.pop("first_name", "Erika")),
        last_name=str(kw.pop("last_name", "Mustermann")),
        joined_at=kw.pop("joined_at", date(2020, 1, 1)),
        status="active",
        created_by=user.id,
        updated_by=user.id,
        **kw,
    )
    db_session.add(member)
    await db_session.flush()
    return member


async def a_template(auth_client: AsyncClient, **overrides: object) -> dict:
    response = await auth_client.post(
        "/api/v1/documents/templates", json=template_payload(**overrides)
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


# --- The placeholder catalogue ---


async def test_the_variable_list_is_the_one_that_validates(
    auth_client: AsyncClient,
) -> None:
    """One catalogue feeds completion, validation and substitution. A second
    list would be a second chance to disagree with the first."""
    response = await auth_client.get("/api/v1/documents/variables")
    assert response.status_code == 200

    keys = {v["key"] for v in response.json()["data"]}
    assert keys == set(variables.VARIABLE_KEYS)
    assert "mitglied.name" in keys


async def test_an_unknown_placeholder_is_refused_on_save(
    auth_client: AsyncClient,
) -> None:
    """Not blanked at print time: a gap on a signed certificate is too late."""
    response = await auth_client.post(
        "/api/v1/documents/templates",
        json=template_payload(body="Hallo {{mitglied.lieblingsfarbe}}"),
    )
    assert response.status_code == 422
    assert "mitglied.lieblingsfarbe" in response.text


async def test_every_unknown_name_is_reported_at_once(
    auth_client: AsyncClient,
) -> None:
    """Telling somebody about one typo at a time is a poor way to edit a letter."""
    response = await auth_client.post(
        "/api/v1/documents/templates",
        json=template_payload(body="{{a.b}} {{c.d}} {{mitglied.name}}"),
    )
    assert response.status_code == 422

    reported = {d["message"] for d in response.json()["details"]}
    assert reported == {"a.b", "c.d"}


async def test_editing_a_template_is_checked_the_same_way(
    auth_client: AsyncClient,
) -> None:
    template = await a_template(auth_client)

    response = await auth_client.patch(
        f"/api/v1/documents/templates/{template['id']}",
        json={"body": "{{mitglied.unbekannt}}"},
    )
    assert response.status_code == 422


async def test_a_brace_in_prose_is_not_a_placeholder(
    auth_client: AsyncClient,
) -> None:
    """The pattern is narrow on purpose, so ordinary text cannot half-match."""
    response = await auth_client.post(
        "/api/v1/documents/templates",
        json=template_payload(body="Öffnungszeiten {mo-fr} und { {} } sowie {{datum}}"),
    )
    assert response.status_code == 201


async def test_the_preview_uses_stand_ins_not_a_real_member(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """Somebody proof-reading wording must not wonder whose data they see."""
    await a_member(db_session, test_tenant, test_user, first_name="Lena", last_name="Fischer")

    response = await auth_client.post(
        "/api/v1/documents/templates/preview", json={"body": "{{mitglied.name}}"}
    )
    assert response.status_code == 200

    rendered = response.json()["data"]["rendered"]
    assert rendered == "Erika Mustermann"
    assert "Lena" not in rendered


async def test_the_preview_lists_unknown_names_rather_than_failing(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.post(
        "/api/v1/documents/templates/preview", json={"body": "{{nope}} {{datum}}"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["unknown"] == ["nope"]


# --- Templates ---


async def test_two_templates_cannot_share_a_name(auth_client: AsyncClient) -> None:
    await a_template(auth_client)

    response = await auth_client.post("/api/v1/documents/templates", json=template_payload())
    assert response.status_code == 409


async def test_inactive_templates_are_hidden_unless_asked_for(
    auth_client: AsyncClient,
) -> None:
    template = await a_template(auth_client)
    await auth_client.patch(
        f"/api/v1/documents/templates/{template['id']}", json={"is_active": False}
    )

    assert (await auth_client.get("/api/v1/documents/templates")).json()["data"] == []
    listed = await auth_client.get("/api/v1/documents/templates?include_inactive=true")
    assert len(listed.json()["data"]) == 1


async def test_another_clubs_template_is_not_found(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    other = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other)
    await db_session.flush()
    foreign = DocumentTemplate(tenant_id=other.id, name="Fremd", title="Fremd", body="Text")
    db_session.add(foreign)
    await db_session.flush()

    assert (await auth_client.get(f"/api/v1/documents/templates/{foreign.id}")).status_code == 404
    assert (
        await auth_client.patch(
            f"/api/v1/documents/templates/{foreign.id}", json={"title": "Meins"}
        )
    ).status_code == 404


async def test_templates_need_a_signed_in_caller(anon_client: AsyncClient) -> None:
    assert (await anon_client.get("/api/v1/documents/templates")).status_code == 403
    assert (await anon_client.get("/api/v1/documents/variables")).status_code == 403


# --- Issuing ---


async def test_issuing_freezes_the_rendered_text(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The whole reason the text is stored rather than referenced."""
    member = await a_member(db_session, test_tenant, test_user)
    template = await a_template(auth_client)

    issued = await auth_client.post(
        f"/api/v1/documents/members/{member.id}/issue",
        json={"template_id": template["id"]},
    )
    assert issued.status_code == 201

    body = issued.json()["data"]["body"]
    assert "Erika Mustermann" in body
    assert "0042" in body
    assert "01.01.2020" in body
    assert "{{" not in body

    # Now the club rewrites the template. What was handed out must not change.
    await auth_client.patch(
        f"/api/v1/documents/templates/{template['id']}",
        json={"body": "Etwas ganz anderes."},
    )

    again = await auth_client.get("/api/v1/documents")
    assert again.json()["data"][0]["body"] == body


async def test_a_verifiable_document_gets_a_code_and_others_do_not(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A code leading to a page that says nothing is worse than no code."""
    member = await a_member(db_session, test_tenant, test_user)
    checkable = await a_template(auth_client, name="Prüfbar")
    plain = await a_template(auth_client, name="Ohne Prüfung", verifiable=False)

    with_code = await auth_client.post(
        f"/api/v1/documents/members/{member.id}/issue",
        json={"template_id": checkable["id"]},
    )
    without = await auth_client.post(
        f"/api/v1/documents/members/{member.id}/issue",
        json={"template_id": plain["id"]},
    )

    assert with_code.json()["data"]["verification_code"]
    assert without.json()["data"]["verification_code"] is None


async def test_an_inactive_template_cannot_be_issued(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    member = await a_member(db_session, test_tenant, test_user)
    template = await a_template(auth_client)
    await auth_client.patch(
        f"/api/v1/documents/templates/{template['id']}", json={"is_active": False}
    )

    response = await auth_client.post(
        f"/api/v1/documents/members/{member.id}/issue",
        json={"template_id": template["id"]},
    )
    assert response.status_code == 409


async def test_a_member_from_another_club_cannot_be_issued_to(
    auth_client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    other = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other)
    await db_session.flush()
    foreign = await a_member(db_session, other, test_user)
    template = await a_template(auth_client)

    response = await auth_client.post(
        f"/api/v1/documents/members/{foreign.id}/issue",
        json={"template_id": template["id"]},
    )
    assert response.status_code == 404


async def test_deleting_a_template_leaves_its_documents_standing(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The issued row carries its own copy of the name and the text."""
    member = await a_member(db_session, test_tenant, test_user)
    template = await a_template(auth_client)
    await auth_client.post(
        f"/api/v1/documents/members/{member.id}/issue",
        json={"template_id": template["id"]},
    )

    deleted = await auth_client.delete(f"/api/v1/documents/templates/{template['id']}")
    assert deleted.status_code == 204

    listed = (await auth_client.get("/api/v1/documents")).json()["data"]
    assert len(listed) == 1
    assert listed[0]["template_id"] is None
    assert listed[0]["template_name"] == "Mitgliedsbescheinigung"
    assert "Erika Mustermann" in listed[0]["body"]


async def test_revoking_keeps_the_document_and_its_text(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The recipient still holds the paper; the trail has to show it existed."""
    member = await a_member(db_session, test_tenant, test_user)
    template = await a_template(auth_client)
    issued = (
        await auth_client.post(
            f"/api/v1/documents/members/{member.id}/issue",
            json={"template_id": template["id"]},
        )
    ).json()["data"]

    revoked = await auth_client.post(
        f"/api/v1/documents/{issued['id']}/revoke", json={"reason": "Falsches Datum"}
    )
    assert revoked.status_code == 200
    assert revoked.json()["data"]["revoked_at"] is not None
    assert revoked.json()["data"]["body"] == issued["body"]

    again = await auth_client.post(
        f"/api/v1/documents/{issued['id']}/revoke", json={"reason": "Nochmal"}
    )
    assert again.status_code == 409


async def test_the_pdf_carries_the_frozen_text(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    member = await a_member(db_session, test_tenant, test_user)
    template = await a_template(auth_client)
    issued = (
        await auth_client.post(
            f"/api/v1/documents/members/{member.id}/issue",
            json={"template_id": template["id"]},
        )
    ).json()["data"]

    response = await auth_client.get(f"/api/v1/documents/{issued['id']}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment")
    # A document about one person has no business in a shared cache.
    assert response.headers["cache-control"] == "no-store"
    assert response.content.startswith(b"%PDF")


# --- The public check page ---


async def test_the_check_page_confirms_a_document_without_showing_it(
    auth_client: AsyncClient,
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """Whoever merely found a code learns it is genuine and nothing further."""
    member = await a_member(db_session, test_tenant, test_user)
    template = await a_template(auth_client)
    issued = (
        await auth_client.post(
            f"/api/v1/documents/members/{member.id}/issue",
            json={"template_id": template["id"]},
        )
    ).json()["data"]

    response = await anon_client.get(f"/verify/{issued['verification_code']}")
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["kind"] == "document"
    assert data["valid"] is True
    assert data["title"] == "Mitgliedsbescheinigung"
    assert data["member_name"] == "E. Mustermann"
    assert data["club_name"] == test_tenant.name
    # The wording itself stays off the page.
    assert "body" not in data
    assert "Mitgliedsnummer" not in response.text


async def test_the_check_page_reports_a_revocation(
    auth_client: AsyncClient,
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    member = await a_member(db_session, test_tenant, test_user)
    template = await a_template(auth_client)
    issued = (
        await auth_client.post(
            f"/api/v1/documents/members/{member.id}/issue",
            json={"template_id": template["id"]},
        )
    ).json()["data"]
    await auth_client.post(f"/api/v1/documents/{issued['id']}/revoke", json={"reason": "Ersetzt"})

    data = (await anon_client.get(f"/verify/{issued['verification_code']}")).json()["data"]
    assert data["valid"] is False
    assert data["revoked"] is True


async def test_an_unknown_code_says_nothing(anon_client: AsyncClient) -> None:
    assert (await anon_client.get("/verify/AAAAAAAAAAA")).status_code == 404


# --- Rendering details ---


async def test_a_missing_value_prints_a_dash_rather_than_a_hole(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """Visible to whoever signs it, and the preview is where it gets caught."""
    member = await a_member(db_session, test_tenant, test_user, birthday=None)
    template = await a_template(auth_client, body="Geboren am {{mitglied.geburtstag}}")

    issued = await auth_client.post(
        f"/api/v1/documents/members/{member.id}/issue",
        json={"template_id": template["id"]},
    )
    assert issued.json()["data"]["body"] == f"Geboren am {variables.EMPTY}"


async def test_the_document_is_dated_in_the_clubs_time_zone(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A certificate dated the 31st because the server runs in UTC is wrong on
    paper in a way nobody would think to check."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    member = await a_member(db_session, test_tenant, test_user)
    template = await a_template(auth_client, body="{{datum}}")

    issued = await auth_client.post(
        f"/api/v1/documents/members/{member.id}/issue",
        json={"template_id": template["id"]},
    )
    club_today = datetime.now(ZoneInfo(test_tenant.timezone)).date()
    assert issued.json()["data"]["body"] == club_today.strftime("%d.%m.%Y")


async def test_the_issued_row_is_scoped_to_the_club(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    member = await a_member(db_session, test_tenant, test_user)
    template = await a_template(auth_client)
    await auth_client.post(
        f"/api/v1/documents/members/{member.id}/issue",
        json={"template_id": template["id"]},
    )

    rows = (await db_session.execute(select(IssuedDocument))).scalars().all()
    assert [r.tenant_id for r in rows] == [test_tenant.id]


async def test_the_preview_date_is_the_clubs_day_too(
    auth_client: AsyncClient, test_tenant: Tenant
) -> None:
    """A preview showing yesterday because the server runs in UTC would send
    somebody looking for a bug in the placeholder."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    response = await auth_client.post(
        "/api/v1/documents/templates/preview", json={"body": "{{datum}}"}
    )
    club_today = datetime.now(ZoneInfo(test_tenant.timezone)).date()
    assert response.json()["data"]["rendered"] == club_today.strftime("%d.%m.%Y")


async def test_the_check_page_dates_the_document_in_the_clubs_day(
    auth_client: AsyncClient,
    anon_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A document issued at 00:30 in Berlin is dated the 11th on the paper and
    must not read as the 10th on the page that checks it."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    member = await a_member(db_session, test_tenant, test_user)
    template = await a_template(auth_client)
    issued = (
        await auth_client.post(
            f"/api/v1/documents/members/{member.id}/issue",
            json={"template_id": template["id"]},
        )
    ).json()["data"]

    data = (await anon_client.get(f"/verify/{issued['verification_code']}")).json()["data"]
    club_today = datetime.now(ZoneInfo(test_tenant.timezone)).date()
    assert data["issued_at"] == club_today.isoformat()
