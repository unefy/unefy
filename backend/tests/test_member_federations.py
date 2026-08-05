"""Member gender field, federation memberships, and the xlsx import parser."""

import json
import uuid
import zipfile
from collections.abc import AsyncGenerator
from datetime import date
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models.member import Member, MemberFederationMembership
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from scripts.import_members_xlsx import excel_serial_to_date, parse_workbook


async def _build_client_for(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    role: str = "owner",
) -> AsyncClient:
    import app.redis as redis_module
    from app.main import app

    async def override_db() -> AsyncGenerator[AsyncSession]:  # type: ignore[type-arg]
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    redis_module._redis_client = fake_redis

    token = uuid.uuid4().hex
    await fake_redis.set(
        f"session:{token}",
        json.dumps(
            {
                "user_id": str(user_id),
                "tenant_id": str(tenant_id),
                "role": role,
            }
        ),
        ex=604800,
    )

    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"unefy_session": token},
    )


def _add_member(tenant_id: uuid.UUID, **overrides: object) -> Member:
    fields: dict[str, object] = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "member_number": uuid.uuid4().hex[:8],
        "first_name": "Alice",
        "last_name": "Example",
        "joined_at": date(2024, 1, 1),
        "status": "active",
    }
    fields.update(overrides)
    return Member(**fields)


# ---------------------------------------------------------------------------
# Gender field on the members API


async def test_create_member_with_gender(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    client = await _build_client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.post(
            "/api/v1/members",
            json={"first_name": "Sarah", "last_name": "Schulze", "gender": "female"},
        )
    assert response.status_code == 201
    assert response.json()["data"]["gender"] == "female"


async def test_create_member_rejects_unknown_gender(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    client = await _build_client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.post(
            "/api/v1/members",
            json={"first_name": "Sarah", "last_name": "Schulze", "gender": "x"},
        )
    assert response.status_code == 422


async def test_update_member_gender(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    member = _add_member(test_tenant.id)
    db_session.add(member)
    await db_session.flush()

    client = await _build_client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.patch(f"/api/v1/members/{member.id}", json={"gender": "male"})
    assert response.status_code == 200
    assert response.json()["data"]["gender"] == "male"


# ---------------------------------------------------------------------------
# Federation memberships endpoint


async def test_list_member_federations(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    member = _add_member(test_tenant.id)
    db_session.add(member)
    await db_session.flush()
    db_session.add(
        MemberFederationMembership(
            tenant_id=test_tenant.id,
            member_id=member.id,
            federation="WSV/DSB",
            federation_number="84839114",
            joined_at=date(2008, 8, 1),
        )
    )
    db_session.add(
        MemberFederationMembership(
            tenant_id=test_tenant.id,
            member_id=member.id,
            federation="GSVBW/BDS",
            federation_number="712954",
        )
    )
    await db_session.flush()

    client = await _build_client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get(f"/api/v1/members/{member.id}/federations")

    assert response.status_code == 200
    data = response.json()["data"]
    assert [f["federation"] for f in data] == ["GSVBW/BDS", "WSV/DSB"]
    assert data[1]["federation_number"] == "84839114"
    assert data[1]["joined_at"] == "2008-08-01"


async def test_member_federations_cross_tenant_returns_404(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    foreign_tenant = Tenant(id=uuid.uuid4(), name="Other", slug="other")
    db_session.add(foreign_tenant)
    await db_session.flush()
    foreign_member = _add_member(foreign_tenant.id)
    db_session.add(foreign_member)
    await db_session.flush()

    client = await _build_client_for(db_session, fake_redis, test_user.id, test_tenant.id)
    async with client as ac:
        response = await ac.get(f"/api/v1/members/{foreign_member.id}/federations")
    assert response.status_code == 404


async def test_member_federations_requires_board_role(
    db_session: AsyncSession,
    fake_redis,  # type: ignore[no-untyped-def]
    test_tenant: Tenant,
    test_user: User,
    test_membership: TenantMembership,
) -> None:
    member = _add_member(test_tenant.id)
    db_session.add(member)
    await db_session.flush()

    client = await _build_client_for(
        db_session, fake_redis, test_user.id, test_tenant.id, role="member"
    )
    async with client as ac:
        response = await ac.get(f"/api/v1/members/{member.id}/federations")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Import parser


def test_excel_serial_to_date() -> None:
    assert excel_serial_to_date("39661") == date(2008, 8, 1)
    # Serials with a time fraction (MitKom exports one) truncate to the day.
    assert excel_serial_to_date("43622.946527777778") == date(2019, 6, 6)


_SHEET1 = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="4"><c r="A4" t="s"><v>0</v></c></row>
<row r="5"><c r="A5" t="s"><v>1</v></c><c r="B5" t="s"><v>2</v></c><c r="G5"><v>84839114</v></c>
<c r="I5" t="s"><v>3</v></c><c r="J5"><v>712954</v></c><c r="K5"><v>39600</v></c></row>
<row r="6"><c r="A6" t="s"><v>4</v></c><c r="B6" t="s"><v>5</v></c><c r="G6"><v>73676915</v></c>
<c r="I6" t="s"><v>6</v></c></row>
</sheetData></worksheet>"""

_SHEET2 = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="2"><c r="A2" t="s"><v>0</v></c></row>
<row r="3"><c r="A3"><v>84839114</v></c><c r="B3" t="s"><v>1</v></c><c r="C3" t="s"><v>2</v></c>
<c r="D3" t="s"><v>7</v></c><c r="E3"><v>70599</v></c><c r="F3" t="s"><v>8</v></c>
<c r="G3"><v>30436</v></c><c r="H3" t="s"><v>9</v></c><c r="J3"><v>39661</v></c>
<c r="K3" t="s"><v>10</v></c></row>
<row r="4"><c r="A4"><v>73676915</v></c><c r="B4" t="s"><v>4</v></c><c r="C4" t="s"><v>5</v></c>
<c r="G4"><v>26185</v></c><c r="H4" t="s"><v>11</v></c><c r="J4"><v>34090</v></c></row>
</sheetData></worksheet>"""

_SHARED = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="12" '
    'uniqueCount="12">'
    "<si><t>Name</t></si><si><t>Bauknecht</t></si><si><t>Uwe</t></si><si><t>ja</t></si>"
    "<si><t>Beck</t></si><si><t>Claudia</t></si><si><t>nein</t></si>"
    "<si><t>Im Wolfer 43</t></si><si><t>Stutgart</t></si><si><t>M</t></si>"
    "<si><t>uwe@example.com</t></si><si><t>W</t></si></sst>"
)


def _write_workbook(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/sharedStrings.xml", _SHARED)
        archive.writestr("xl/worksheets/sheet1.xml", _SHEET1)
        archive.writestr("xl/worksheets/sheet2.xml", _SHEET2)


def test_parse_workbook(tmp_path: Path) -> None:
    workbook = tmp_path / "members.xlsx"
    _write_workbook(workbook)

    rows = parse_workbook(str(workbook))

    assert len(rows) == 2
    first, second = rows

    assert (first.first_name, first.last_name) == ("Uwe", "Bauknecht")
    assert first.city == "Stuttgart"  # typo in the source is corrected
    assert first.birthday == date(1983, 4, 30)
    assert first.gender == "male"
    assert first.email == "uwe@example.com"
    assert first.joined_at == date(2008, 8, 1)
    # WSV/DSB from the MitKom sheet plus GSVBW/BDS from the manual sheet.
    assert [(f.federation, f.number) for f in first.federations] == [
        ("WSV/DSB", "84839114"),
        ("GSVBW/BDS", "712954"),
    ]
    assert first.federations[1].joined_at == date(2008, 6, 1)

    assert (second.first_name, second.last_name) == ("Claudia", "Beck")
    assert second.gender == "female"
    assert second.email is None
    # "nein" in the membership column → no BDS row.
    assert [f.federation for f in second.federations] == ["WSV/DSB"]
