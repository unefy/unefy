"""Idempotent seed script: tenant "Testverein" with members, fees, dues and SEPA data.

Run inside the backend container:
    uv run python scripts/seed_testdata.py
"""

import asyncio
import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.seeds import member_statuses_seed
from app.database import async_session_factory
from app.models.competition import Competition, Entry, Session
from app.models.due import Due, FeeType, MemberFee
from app.models.event import Event, EventRegistration
from app.models.member import Member
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from app.services.member import format_member_number

OWNER_EMAIL = "andreas@widmer.im"
TENANT_SLUG = "testverein"

FIRST_NAMES = [
    "Thomas",
    "Sabine",
    "Michael",
    "Claudia",
    "Stefan",
    "Petra",
    "Andreas",
    "Monika",
    "Jürgen",
    "Karin",
    "Markus",
    "Susanne",
    "Frank",
    "Birgit",
    "Peter",
    "Andrea",
    "Wolfgang",
    "Martina",
    "Christian",
    "Nicole",
    "Matthias",
    "Julia",
    "Daniel",
    "Katrin",
    "Lukas",
    "Lena",
    "Felix",
    "Anna",
    "Jonas",
    "Laura",
]
LAST_NAMES = [
    "Müller",
    "Schmidt",
    "Schneider",
    "Fischer",
    "Weber",
    "Meyer",
    "Wagner",
    "Becker",
    "Schulz",
    "Hoffmann",
    "Koch",
    "Bauer",
    "Richter",
    "Klein",
    "Wolf",
    "Schröder",
    "Neumann",
    "Schwarz",
    "Zimmermann",
    "Braun",
    "Krüger",
    "Hofmann",
    "Hartmann",
    "Lange",
    "Schmitt",
    "Werner",
    "Krause",
    "Lehmann",
    "Köhler",
    "Maier",
]
CITIES = [
    ("70173", "Stuttgart"),
    ("70190", "Stuttgart"),
    ("71032", "Böblingen"),
    ("71063", "Sindelfingen"),
    ("72070", "Tübingen"),
    ("73728", "Esslingen"),
    ("70794", "Filderstadt"),
    ("70563", "Stuttgart"),
]
STREETS = [
    "Hauptstraße",
    "Gartenweg",
    "Schillerstraße",
    "Goethestraße",
    "Bahnhofstraße",
    "Lindenweg",
    "Mozartstraße",
    "Waldstraße",
]

FEE_TYPES = [
    ("Erwachsene", "Jahresbeitrag für erwachsene Mitglieder", Decimal("120.00"), "yearly"),
    ("Jugend", "Ermäßigter Jahresbeitrag für Jugendliche unter 18", Decimal("60.00"), "yearly"),
    ("Familie", "Jahresbeitrag für Familienmitgliedschaften", Decimal("180.00"), "yearly"),
    ("Aufnahmegebühr", "Einmalige Gebühr bei Vereinsbeitritt", Decimal("25.00"), "one_time"),
]

BANKS = [
    ("60050101", "SOLADEST600"),  # BW-Bank
    ("64150020", "SOLADES1TUB"),  # KSK Tübingen
    ("60250010", "SOLADES1WBN"),  # KSK Waiblingen
    ("43060967", "GENODEM1GLS"),  # GLS Bank
]


def _fake_iban(rng: random.Random) -> tuple[str, str]:
    blz, bic = rng.choice(BANKS)
    account = str(rng.randint(1, 9999999999)).zfill(10)
    check = str(rng.randint(10, 99))
    return f"DE{check}{blz}{account}", bic


async def _ensure_tenant(session: AsyncSession, rng: random.Random) -> Tenant:
    result = await session.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(
            name="Testverein",
            short_name="TV",
            slug=TENANT_SLUG,
            email="info@testverein.example",
            city="Stuttgart",
            zip_code="70173",
            street="Vereinsweg 1",
            member_number_format="TV-{NUM:3}",
            member_statuses=member_statuses_seed("de"),
        )
        session.add(tenant)
        await session.flush()
        print("Created tenant 'Testverein'.")

    if not tenant.sepa_creditor_id:
        tenant.sepa_creditor_id = "DE98ZZZ09999999999"
        tenant.iban = "DE02600501010002034304"
        tenant.bic = "SOLADEST600"
        print("Set SEPA creditor data on tenant.")
    return tenant


async def _ensure_owner(session: AsyncSession, tenant: Tenant) -> User:
    result = await session.execute(select(User).where(User.email == OWNER_EMAIL))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=OWNER_EMAIL,
            name="Andreas Widmer",
            email_verified=True,
            locale="de",
        )
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


async def _ensure_members(
    session: AsyncSession, tenant: Tenant, user: User, rng: random.Random
) -> list[Member]:
    result = await session.execute(
        select(Member).where(Member.tenant_id == tenant.id, Member.deleted_at.is_(None))
    )
    members = list(result.scalars().all())
    if members:
        return members

    statuses = ["active"] * 20 + ["inactive"] * 3 + ["resigned"] * 2
    rng.shuffle(statuses)
    num = tenant.member_number_next
    for i, status in enumerate(statuses):
        first = FIRST_NAMES[i % len(FIRST_NAMES)]
        last = LAST_NAMES[i % len(LAST_NAMES)]
        last_slug = last.lower().replace("ö", "oe").replace("ü", "ue")
        zip_code, city = rng.choice(CITIES)
        birth_year = 1976 + rng.randint(0, 32)
        birthday = date(birth_year, rng.randint(1, 12), rng.randint(1, 28))
        joined = date(rng.randint(2005, 2025), rng.randint(1, 12), rng.randint(1, 28))
        member = Member(
            tenant_id=tenant.id,
            member_number=format_member_number(tenant.member_number_format, num),
            first_name=first,
            last_name=last,
            email=f"{first.lower()}.{last_slug}@example.com",
            phone=f"+49 711 {rng.randint(100000, 999999)}",
            birthday=birthday,
            street=f"{rng.choice(STREETS)} {rng.randint(1, 99)}",
            zip_code=zip_code,
            city=city,
            country="Deutschland",
            joined_at=joined,
            left_at=date(2025, rng.randint(1, 12), 28) if status == "resigned" else None,
            status=status,
            created_by=user.id,
            updated_by=user.id,
        )
        session.add(member)
        members.append(member)
        num += 1

    tenant.member_number_next = num
    await session.flush()
    print(f"Created {len(members)} members.")
    return members


def _ensure_member_sepa(members: list[Member], rng: random.Random) -> None:
    updated = 0
    for member in members:
        if member.iban or member.status != "active":
            continue
        # ~75% of active members pay via SEPA direct debit.
        # Deterministic per member so re-runs don't add more mandates.
        if sum(ord(c) for c in member.member_number) % 4 == 0:
            continue
        iban, bic = _fake_iban(rng)
        member.iban = iban
        member.bic = bic
        member.account_holder = f"{member.first_name} {member.last_name}"
        member.sepa_mandate_reference = f"TV-M-{member.member_number}"
        mandate_year = max(member.joined_at.year, 2020)
        member.sepa_mandate_date = date(mandate_year, rng.randint(1, 12), rng.randint(1, 28))
        updated += 1
    if updated:
        print(f"Added SEPA bank data and mandates to {updated} members.")


async def _ensure_fee_types(
    session: AsyncSession, tenant: Tenant, user: User
) -> dict[str, FeeType]:
    result = await session.execute(
        select(FeeType).where(FeeType.tenant_id == tenant.id, FeeType.deleted_at.is_(None))
    )
    existing = {ft.name: ft for ft in result.scalars().all()}
    created = 0
    for name, description, amount, interval in FEE_TYPES:
        if name in existing:
            continue
        fee_type = FeeType(
            tenant_id=tenant.id,
            name=name,
            description=description,
            amount=amount,
            interval=interval,
            is_active=True,
            created_by=user.id,
            updated_by=user.id,
        )
        session.add(fee_type)
        existing[name] = fee_type
        created += 1
    if created:
        await session.flush()
        print(f"Created {created} fee types.")
    return existing


def _fee_for_member(member: Member, rng: random.Random) -> str:
    if member.birthday and member.birthday > date(2008, 1, 1):
        return "Jugend"
    return "Familie" if rng.random() < 0.2 else "Erwachsene"


async def _ensure_member_fees(
    session: AsyncSession,
    tenant: Tenant,
    user: User,
    members: list[Member],
    fee_types: dict[str, FeeType],
    rng: random.Random,
) -> dict[str, str]:
    """Assign a yearly fee to every active member. Returns member_id → fee name."""
    result = await session.execute(
        select(MemberFee).where(MemberFee.tenant_id == tenant.id, MemberFee.deleted_at.is_(None))
    )
    fee_name_by_id = {ft.id: name for name, ft in fee_types.items()}
    assigned = {mf.member_id: fee_name_by_id[mf.fee_type_id] for mf in result.scalars().all()}
    fee_by_member: dict[str, str] = {}
    created = 0
    for member in members:
        if member.status != "active":
            continue
        # Existing assignments win so re-runs stay stable.
        fee_name = assigned.get(member.id) or _fee_for_member(member, rng)
        fee_by_member[str(member.id)] = fee_name
        if member.id in assigned:
            continue
        session.add(
            MemberFee(
                tenant_id=tenant.id,
                member_id=member.id,
                fee_type_id=fee_types[fee_name].id,
                valid_from=date(max(member.joined_at.year, 2024), 1, 1),
                created_by=user.id,
                updated_by=user.id,
            )
        )
        created += 1
    if created:
        await session.flush()
        print(f"Assigned fee types to {created} members.")
    return fee_by_member


async def _ensure_dues(
    session: AsyncSession,
    tenant: Tenant,
    user: User,
    members: list[Member],
    fee_types: dict[str, FeeType],
    fee_by_member: dict[str, str],
    rng: random.Random,
) -> None:
    result = await session.execute(select(Due).where(Due.tenant_id == tenant.id))
    existing = {(d.member_id, d.fee_type_id, d.period_start) for d in result.scalars().all()}

    created = 0
    for member in members:
        fee_name = fee_by_member.get(str(member.id))
        if not fee_name:
            continue
        fee_type = fee_types[fee_name]
        for year in (2025, 2026):
            period_start = date(year, 1, 1)
            if (member.id, fee_type.id, period_start) in existing:
                continue

            if year == 2025:
                # Last year: almost everything settled, a few cancelled
                roll = rng.random()
                status = "cancelled" if roll < 0.05 else "paid"
            else:
                # Current year: mixed open/paid
                roll = rng.random()
                status = "open" if roll < 0.45 else "paid"

            paid_at = None
            payment_method = None
            if status == "paid":
                paid_at = date(year, rng.randint(1, 3), rng.randint(1, 28))
                if member.sepa_mandate_reference:
                    payment_method = "sepa"
                else:
                    payment_method = rng.choice(["bank_transfer", "cash"])

            session.add(
                Due(
                    tenant_id=tenant.id,
                    member_id=member.id,
                    fee_type_id=fee_type.id,
                    fee_name=fee_type.name,
                    amount=fee_type.amount,
                    period_start=period_start,
                    period_end=date(year, 12, 31),
                    due_date=date(year, 1, 31),
                    status=status,
                    paid_at=paid_at,
                    payment_method=payment_method,
                    note="Storniert wegen Beitragsbefreiung" if status == "cancelled" else None,
                    created_by=user.id,
                    updated_by=user.id,
                )
            )
            created += 1
    if created:
        print(f"Created {created} dues (2025 + 2026).")


def _score(rng: random.Random, base: int, spread: int = 25) -> Decimal:
    return Decimal(base + rng.randint(0, spread))


def _add_entries(
    session_obj: Session,
    members: list[Member],
    tenant: Tenant,
    user: User,
    rng: random.Random,
    *,
    base_score: int,
) -> list[Entry]:
    entries = []
    for member in members:
        entries.append(
            Entry(
                tenant_id=tenant.id,
                session_id=session_obj.id,
                member_id=member.id,
                score_value=_score(rng, base_score),
                score_unit="Ringe",
                discipline=session_obj.discipline,
                source="manual",
                recorded_by=user.id,
                recorded_at=datetime(
                    session_obj.date.year,
                    session_obj.date.month,
                    session_obj.date.day,
                    19,
                    30,
                    tzinfo=UTC,
                ),
                created_by=user.id,
                updated_by=user.id,
            )
        )
    return entries


async def _ensure_competitions(
    session: AsyncSession,
    tenant: Tenant,
    user: User,
    members: list[Member],
    rng: random.Random,
) -> None:
    result = await session.execute(
        select(Competition).where(
            Competition.tenant_id == tenant.id, Competition.deleted_at.is_(None)
        )
    )
    if result.scalars().first() is not None:
        return

    active = [m for m in members if m.status == "active"]
    audit = {"created_by": user.id, "updated_by": user.id}

    # 1) Club championship with two disciplines and past + upcoming rounds
    championship = Competition(
        tenant_id=tenant.id,
        name="Vereinsmeisterschaft 2026",
        description="Offene Vereinsmeisterschaft in zwei Disziplinen.",
        competition_type="competition",
        start_date=date(2026, 3, 7),
        end_date=date(2026, 9, 26),
        scoring_mode="highest_wins",
        scoring_unit="Ringe",
        disciplines=["Luftgewehr 10m", "Luftpistole 10m"],
        **audit,
    )
    session.add(championship)
    await session.flush()

    vm_sessions = [
        ("Durchgang 1", date(2026, 3, 7), "Luftgewehr 10m"),
        ("Durchgang 2", date(2026, 5, 16), "Luftgewehr 10m"),
        ("Durchgang 3", date(2026, 7, 11), "Luftpistole 10m"),
        ("Finale", date(2026, 9, 26), "Luftgewehr 10m"),
    ]
    for name, session_date, discipline in vm_sessions:
        s = Session(
            tenant_id=tenant.id,
            competition_id=championship.id,
            name=name,
            date=session_date,
            location="Schießstand Vereinsheim",
            discipline=discipline,
            **audit,
        )
        session.add(s)
        await session.flush()
        if session_date <= date(2026, 7, 26):
            participants = rng.sample(active, k=min(12, len(active)))
            base = 340 if discipline == "Luftgewehr 10m" else 320
            for entry in _add_entries(s, participants, tenant, user, rng, base_score=base):
                session.add(entry)

    # 2) League (Rundenwettkampf) across the winter season
    league = Competition(
        tenant_id=tenant.id,
        name="Rundenwettkampf Luftgewehr 2025/26",
        description="Kreisliga A — Mannschaftswettkampf über 6 Runden.",
        competition_type="league",
        start_date=date(2025, 10, 1),
        end_date=date(2026, 4, 30),
        scoring_mode="highest_wins",
        scoring_unit="Ringe",
        disciplines=["Luftgewehr 10m"],
        **audit,
    )
    session.add(league)
    await session.flush()

    team = rng.sample(active, k=min(5, len(active)))
    round_dates = [
        date(2025, 10, 18),
        date(2025, 11, 15),
        date(2025, 12, 13),
        date(2026, 1, 17),
        date(2026, 2, 21),
        date(2026, 3, 21),
    ]
    for i, round_date in enumerate(round_dates, start=1):
        s = Session(
            tenant_id=tenant.id,
            competition_id=league.id,
            name=f"{i}. Runde",
            date=round_date,
            location="Schießstand Vereinsheim" if i % 2 else "SV Musterhausen",
            discipline="Luftgewehr 10m",
            **audit,
        )
        session.add(s)
        await session.flush()
        if round_date <= date(2026, 7, 26):
            for entry in _add_entries(s, team, tenant, user, rng, base_score=350):
                session.add(entry)

    # 3) Training series with recent results
    training = Competition(
        tenant_id=tenant.id,
        name="Trainingsabende 2026",
        description="Wöchentliches Training mit Ergebniserfassung.",
        competition_type="training",
        start_date=date(2026, 1, 8),
        end_date=None,
        scoring_mode="highest_wins",
        scoring_unit="Ringe",
        disciplines=["Luftgewehr 10m", "Luftpistole 10m"],
        **audit,
    )
    session.add(training)
    await session.flush()

    for week in range(4):
        training_date = date(2026, 7, 2) + timedelta(days=7 * week)
        s = Session(
            tenant_id=tenant.id,
            competition_id=training.id,
            name=None,
            date=training_date,
            location="Schießstand Vereinsheim",
            discipline="Luftgewehr 10m",
            **audit,
        )
        session.add(s)
        await session.flush()
        if training_date <= date(2026, 7, 26):
            participants = rng.sample(active, k=min(8, len(active)))
            for entry in _add_entries(s, participants, tenant, user, rng, base_score=330):
                session.add(entry)

    print("Created 3 competitions with sessions and results.")


async def _ensure_events(
    session: AsyncSession,
    tenant: Tenant,
    user: User,
    members: list[Member],
    rng: random.Random,
) -> None:
    result = await session.execute(
        select(Event).where(Event.tenant_id == tenant.id, Event.deleted_at.is_(None))
    )
    if result.scalars().first() is not None:
        return

    active = [m for m in members if m.status == "active"]
    audit = {"created_by": user.id, "updated_by": user.id}

    def dt(y: int, mo: int, d: int, h: int = 0, mi: int = 0) -> datetime:
        return datetime(y, mo, d, h, mi, tzinfo=UTC)

    events = [
        Event(
            tenant_id=tenant.id,
            title="Jahreshauptversammlung 2026",
            description="Ordentliche Mitgliederversammlung mit Vorstandswahlen.",
            event_type="meeting",
            location="Vereinsheim, großer Saal",
            starts_at=dt(2026, 2, 20, 19, 0),
            ends_at=dt(2026, 2, 20, 22, 0),
            **audit,
        ),
        Event(
            tenant_id=tenant.id,
            title="Frühjahrs-Arbeitseinsatz",
            description="Instandhaltung Schießstand und Außenanlage.",
            event_type="other",
            location="Vereinsheim",
            starts_at=dt(2026, 4, 11, 9, 0),
            ends_at=dt(2026, 4, 11, 14, 0),
            **audit,
        ),
        Event(
            tenant_id=tenant.id,
            title="Sommerfest 2026",
            description="Vereinsfest mit Grillen, Preisschießen und Tombola.",
            event_type="celebration",
            location="Festwiese am Vereinsheim",
            starts_at=dt(2026, 8, 15, 11, 0),
            ends_at=dt(2026, 8, 15, 22, 0),
            registration_required=True,
            registration_deadline=dt(2026, 8, 1, 23, 59),
            max_participants=40,
            **audit,
        ),
        Event(
            tenant_id=tenant.id,
            title="Weihnachtsfeier 2026",
            description="Jahresabschluss mit Ehrungen langjähriger Mitglieder.",
            event_type="celebration",
            location="Gasthof Adler",
            starts_at=dt(2026, 12, 5, 18, 0),
            ends_at=dt(2026, 12, 5, 23, 0),
            registration_required=True,
            registration_deadline=dt(2026, 11, 27, 23, 59),
            max_participants=60,
            **audit,
        ),
        Event(
            tenant_id=tenant.id,
            title="Bezirksschützentag 2026",
            description="Abgesagt wegen Renovierung der Bezirkssportanlage.",
            event_type="other",
            location="Bezirkssportanlage",
            starts_at=dt(2026, 10, 3),
            all_day=True,
            status="cancelled",
            **audit,
        ),
    ]
    for week in range(3):
        start = dt(2026, 7, 30, 19, 0) + timedelta(days=7 * week)
        events.append(
            Event(
                tenant_id=tenant.id,
                title="Training Luftgewehr",
                description="Offenes Training für alle Mitglieder.",
                event_type="training",
                location="Schießstand Vereinsheim",
                starts_at=start,
                ends_at=start + timedelta(hours=2),
                **audit,
            )
        )
    session.add_all(events)
    await session.flush()

    registrations = 0
    for event in events:
        if not event.registration_required:
            continue
        participants = rng.sample(active, k=min(rng.randint(12, 16), len(active)))
        for i, member in enumerate(participants):
            session.add(
                EventRegistration(
                    tenant_id=tenant.id,
                    event_id=event.id,
                    member_id=member.id,
                    status="waitlist" if i >= 14 else "registered",
                    **audit,
                )
            )
            registrations += 1

    print(f"Created {len(events)} events with {registrations} registrations.")


async def main() -> None:
    rng = random.Random(1976)
    async with async_session_factory() as session:
        tenant = await _ensure_tenant(session, rng)
        user = await _ensure_owner(session, tenant)
        members = await _ensure_members(session, tenant, user, rng)
        _ensure_member_sepa(members, rng)
        fee_types = await _ensure_fee_types(session, tenant, user)
        fee_by_member = await _ensure_member_fees(session, tenant, user, members, fee_types, rng)
        await _ensure_dues(session, tenant, user, members, fee_types, fee_by_member, rng)
        await _ensure_competitions(session, tenant, user, members, rng)
        await _ensure_events(session, tenant, user, members, rng)
        await session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
