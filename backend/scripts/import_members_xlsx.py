"""Idempotent import of the SVES member list from the MitKom Excel export.

Reads `Mitgliederliste_2026.xlsx` (sheet "MitKom-Import" for personal data,
sheet "Tabelle1" for the GSVBW/BDS second federation), creates the tenant if
needed and upserts members and their federation memberships.

Run inside the backend container:
    uv run python scripts/import_members_xlsx.py /path/to/Mitgliederliste_2026.xlsx

The xlsx is parsed with the standard library on purpose — a one-file import
does not justify an openpyxl dependency.
"""

import argparse
import asyncio
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from xml.etree import ElementTree as ET

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.seeds import member_statuses_seed
from app.database import async_session_factory
from app.models.member import Member, MemberFederationMembership
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from app.services.member import format_member_number

OWNER_EMAIL = "andreas@widmer.im"
TENANT_SLUG = "sves"
TENANT_NAME = "Schützenverein Ehemalige Soldaten e.V."
TENANT_SHORT = "SVES"
MEMBER_NUMBER_FORMAT = "SVES-{NUM:3}"

FEDERATION_PRIMARY = "WSV/DSB"
FEDERATION_SECONDARY = "GSVBW/BDS"

# Obvious typos in the source list, fixed on the way in. Keys are the exact
# source values so an already-correct row is never touched.
CITY_CORRECTIONS = {
    "Stutgart": "Stuttgart",
    "Ostfilden": "Ostfildern",
    "Offenbachan der Queich": "Offenbach an der Queich",
}

GENDERS = {"M": "male", "W": "female", "D": "diverse"}

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_T = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"

# Excel serials count days from this epoch (1900 date system, incl. the
# fictitious 1900-02-29 that the offset to 1899-12-30 already absorbs).
_EXCEL_EPOCH = date(1899, 12, 30)


def excel_serial_to_date(value: str) -> date:
    """Convert an Excel date serial ("39661" or "43622.94…") to a date."""
    return _EXCEL_EPOCH + timedelta(days=int(float(value)))


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        raw = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(raw)
    return ["".join(t.text or "" for t in si.iter(_T)) for si in root.findall("m:si", _NS)]


def read_sheet(path: str, sheet_file: str) -> list[dict[str, str]]:
    """Rows of one worksheet as {column letter: cell text}. Empty rows dropped."""
    with zipfile.ZipFile(path) as archive:
        shared = _read_shared_strings(archive)
        root = ET.fromstring(archive.read(f"xl/worksheets/{sheet_file}"))
    rows: list[dict[str, str]] = []
    sheet_data = root.find("m:sheetData", _NS)
    if sheet_data is None:
        return rows
    for row in sheet_data.findall("m:row", _NS):
        cells: dict[str, str] = {}
        for cell in row.findall("m:c", _NS):
            value_el = cell.find("m:v", _NS)
            if value_el is None or value_el.text is None:
                continue
            value = value_el.text
            if cell.get("t") == "s":
                value = shared[int(value)]
            column = "".join(ch for ch in (cell.get("r") or "") if ch.isalpha())
            cells[column] = value
        if cells:
            rows.append(cells)
    return rows


@dataclass
class FederationRow:
    federation: str
    number: str | None
    joined_at: date | None


@dataclass
class MemberRow:
    first_name: str
    last_name: str
    street: str | None
    zip_code: str | None
    city: str | None
    birthday: date | None
    gender: str | None
    email: str | None
    joined_at: date | None
    federations: list[FederationRow] = field(default_factory=list)


def parse_workbook(path: str) -> list[MemberRow]:
    """Members from the MitKom sheet, enriched with the BDS sheet.

    Sheet2 ("MitKom-Import") is the federation's own export and wins for all
    personal data; sheet1 ("Tabelle1") only contributes the GSVBW/BDS
    membership. Rows are joined on the WSV/DSB number, which both sheets carry.
    """
    mitkom = read_sheet(path, "sheet2.xml")
    manual = read_sheet(path, "sheet1.xml")

    bds_by_wsv: dict[str, FederationRow] = {}
    for row in manual:
        wsv_number = row.get("G")
        if not wsv_number or not wsv_number.isdigit():
            continue  # header and note rows
        if row.get("I", "").strip().lower() != "ja":
            continue
        bds_by_wsv[wsv_number] = FederationRow(
            federation=FEDERATION_SECONDARY,
            number=row.get("J"),
            joined_at=excel_serial_to_date(row["K"]) if row.get("K") else None,
        )

    members: list[MemberRow] = []
    for row in mitkom:
        wsv_number = row.get("A")
        if not wsv_number or not wsv_number.isdigit():
            continue  # title and header rows
        joined = excel_serial_to_date(row["J"]) if row.get("J") else None
        city = row.get("F")
        member = MemberRow(
            first_name=row["C"].strip(),
            last_name=row["B"].strip(),
            street=row.get("D", "").strip() or None,
            zip_code=row.get("E"),
            city=CITY_CORRECTIONS.get(city, city) if city else None,
            birthday=excel_serial_to_date(row["G"]) if row.get("G") else None,
            gender=GENDERS.get(row.get("H", "").strip().upper()),
            email=row.get("K", "").strip() or None,
            joined_at=joined,
            federations=[
                FederationRow(federation=FEDERATION_PRIMARY, number=wsv_number, joined_at=joined)
            ],
        )
        if wsv_number in bds_by_wsv:
            member.federations.append(bds_by_wsv[wsv_number])
        members.append(member)
    return members


async def _ensure_tenant(session: AsyncSession) -> Tenant:
    result = await session.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(
            name=TENANT_NAME,
            short_name=TENANT_SHORT,
            slug=TENANT_SLUG,
            member_number_format=MEMBER_NUMBER_FORMAT,
            member_statuses=member_statuses_seed("de"),
        )
        session.add(tenant)
        await session.flush()
        print(f"Created tenant '{TENANT_NAME}'.")
    return tenant


async def _ensure_owner(session: AsyncSession, tenant: Tenant) -> User:
    result = await session.execute(select(User).where(User.email == OWNER_EMAIL))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=OWNER_EMAIL, name="Andreas Widmer", email_verified=True, locale="de")
        session.add(user)
        await session.flush()
        print(f"Created user {OWNER_EMAIL}.")
    membership = await session.execute(
        select(TenantMembership).where(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == tenant.id,
        )
    )
    if membership.scalar_one_or_none() is None:
        session.add(TenantMembership(user_id=user.id, tenant_id=tenant.id, role="owner"))
        print(f"Added owner membership for {OWNER_EMAIL}.")
    return user


async def _import_members(
    session: AsyncSession, tenant: Tenant, user: User, rows: list[MemberRow]
) -> None:
    result = await session.execute(
        select(Member).where(Member.tenant_id == tenant.id, Member.deleted_at.is_(None))
    )
    existing = {(m.last_name, m.first_name, m.birthday): m for m in result.scalars().all()}
    fed_result = await session.execute(
        select(MemberFederationMembership).where(
            MemberFederationMembership.tenant_id == tenant.id,
            MemberFederationMembership.deleted_at.is_(None),
        )
    )
    existing_feds = {(f.member_id, f.federation) for f in fed_result.scalars().all()}

    created = updated = feds_created = 0
    num = tenant.member_number_next
    for row in rows:
        key = (row.last_name, row.first_name, row.birthday)
        member = existing.get(key)
        if member is None:
            member = Member(
                tenant_id=tenant.id,
                member_number=format_member_number(tenant.member_number_format, num),
                first_name=row.first_name,
                last_name=row.last_name,
                email=row.email,
                birthday=row.birthday,
                gender=row.gender,
                street=row.street,
                zip_code=row.zip_code,
                city=row.city,
                country="Deutschland",
                joined_at=row.joined_at or date.today(),
                status="active",
                created_by=user.id,
                updated_by=user.id,
            )
            session.add(member)
            await session.flush()
            existing[key] = member
            num += 1
            created += 1
        else:
            # Re-runs refresh master data from the source of truth.
            member.email = row.email
            member.gender = row.gender
            member.street = row.street
            member.zip_code = row.zip_code
            member.city = row.city
            if row.joined_at:
                member.joined_at = row.joined_at
            updated += 1

        for fed in row.federations:
            if (member.id, fed.federation) in existing_feds:
                continue
            session.add(
                MemberFederationMembership(
                    tenant_id=tenant.id,
                    member_id=member.id,
                    federation=fed.federation,
                    federation_number=fed.number,
                    joined_at=fed.joined_at,
                    created_by=user.id,
                    updated_by=user.id,
                )
            )
            existing_feds.add((member.id, fed.federation))
            feds_created += 1

    tenant.member_number_next = num
    print(
        f"Members: {created} created, {updated} refreshed. "
        f"Federation memberships: {feds_created} created."
    )


async def run(path: str) -> None:
    rows = parse_workbook(path)
    if not rows:
        print("No member rows found in the workbook.", file=sys.stderr)
        raise SystemExit(1)
    async with async_session_factory() as session:
        tenant = await _ensure_tenant(session)
        user = await _ensure_owner(session, tenant)
        await _import_members(session, tenant, user, rows)
        await session.commit()
        print("Import complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", help="Path to Mitgliederliste_2026.xlsx")
    args = parser.parse_args()
    asyncio.run(run(args.xlsx))


if __name__ == "__main__":
    main()
