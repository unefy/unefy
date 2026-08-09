"""Idempotent seed script: tenant "Testverein" with members, fees, dues and SEPA data.

Run inside the backend container:
    uv run python scripts/seed_testdata.py
"""

import asyncio
import math
import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.seeds import member_statuses_seed
from app.database import async_session_factory
from app.dependencies import AuthContext
from app.models.attendance import AttendanceRecord, AttendanceSession
from app.models.catalog import ClubDiscipline
from app.models.competition import Competition, Entry, Session
from app.models.due import Due, FeeType, MemberFee
from app.models.event import Event, EventRegistration
from app.models.member import Member
from app.models.shooting import (
    ShootingProofCertificate,
    ShootingProofRule,
    ShootingRecordDetail,
)
from app.models.target_type import TargetType
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from app.schemas.competition import FREE_TRAINING_TYPE
from app.schemas.shooting import CertificateIssue
from app.services.member import format_member_number
from app.services.proof_chain import append_entry, session_close_hash
from app.services.scoring import ShotInput, TargetGeometry, score_series
from app.services.shooting import ShootingService
from app.services.shot_entry import FREE_TRAINING_NAME

OWNER_EMAIL = "andreas@widmer.im"
TENANT_SLUG = "testverein"

#: The title every seeded training evening carries, and the marker that says
#: the attendance history has already been written.
TRAINING_TITLE = "Übungsabend"

#: Above this many scored series the club counts as seeded. Well clear of what
#: manual testing leaves behind, well below what one run creates.
SEEDED_SERIES_MARKER = 20

FOREIGN_RANGES = (
    "SV Nachbarort, Stand 2",
    "Schützenhaus Musterhausen",
    "KKS Talheim, 50m",
)

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


# --- Attendance, shooting details and the §14 proof ---

#: A training evening every week, plus the odd Saturday match — enough history
#: for a 12-month proof window to have something to say.
TRAINING_WEEKS = 62

#: Roughly how many of the active members turn up on an ordinary evening.
ATTENDANCE_SHARE = 0.45

WEAPON_CATEGORIES = ("kurzwaffe", "langwaffe", "luftdruck")

#: Target slug per discipline name, so a recorded series is scored on the
#: geometry that discipline is actually shot on.
TARGET_BY_DISCIPLINE = {
    "Luftgewehr 10m": "air_rifle_10m",
    "Luftpistole 10m": "air_pistol_10m",
    "BDS Pistole 25m Präzision": "sport_pistol_25m",
    "BDS KK-Pistole 25m": "sport_pistol_25m",
}

#: Which weapon category the range book gets for a discipline. Air weapons are
#: their own category in §14 terms, which is why this is not derived from the
#: target alone.
WEAPON_BY_DISCIPLINE = {
    "Luftgewehr 10m": "luftdruck",
    "Luftpistole 10m": "luftdruck",
    "BDS Pistole 25m Präzision": "kurzwaffe",
    "BDS KK-Pistole 25m": "kurzwaffe",
}


def _training_dates(today: date, weeks: int) -> list[date]:
    """Every Wednesday evening going back `weeks`, oldest first."""
    latest = today - timedelta(days=(today.weekday() - 2) % 7)
    return sorted(latest - timedelta(weeks=offset) for offset in range(weeks))


def _shots_for(
    rng: random.Random, geometry: TargetGeometry, count: int, skill: float
) -> list[ShotInput]:
    """A plausible group, tighter for a better shooter.

    Polar rather than two independent normals: a real group is round, and
    sampling x and y separately produces a cross. `skill` runs 0..1 and scales
    the spread — the ring values fall out of the geometry afterwards, so they
    stay consistent with what the app would compute for the same holes.
    """
    # Ring 10's radius is the unit the spread is expressed in.
    ten_radius = geometry.ring_diameters_mm[0] / 2
    outer_radius = geometry.ring_diameters_mm[-1] / 2
    spread = ten_radius + (outer_radius - ten_radius) * (1.0 - skill) * 0.55

    shots = []
    for _ in range(count):
        # Normalised to the ring-1 radius, the convention the API stores.
        radius_mm = abs(rng.gauss(0, spread))
        angle = rng.uniform(0, 2 * math.pi)
        shots.append(
            ShotInput(
                x=(radius_mm * math.cos(angle)) / outer_radius,
                y=(radius_mm * math.sin(angle)) / outer_radius,
            )
        )
    return shots


async def _ensure_attendance(
    session: AsyncSession,
    tenant: Tenant,
    user: User,
    members: list[Member],
    rng: random.Random,
) -> list[AttendanceRecord]:
    """Training evenings with the people who were there.

    Closed for every date in the past, and closed the way the service closes
    them — final record hash plus a link in the proof chain — so the chain
    verifies instead of showing a hole where the seed wrote history.
    """
    active = [m for m in members if m.status == "active"]
    supervisors = active[:4]
    today = datetime.now(UTC).date()
    dates = _training_dates(today, TRAINING_WEEKS)
    oldest = datetime(dates[0].year, dates[0].month, dates[0].day, 23, 59, tzinfo=UTC)

    # The oldest evening is the marker: a club that has it has the whole run.
    # Checking merely for "a session called Übungsabend" would let one
    # hand-made evening suppress the entire history.
    already = (
        (
            await session.execute(
                select(AttendanceSession)
                .where(AttendanceSession.tenant_id == tenant.id)
                .where(AttendanceSession.title == TRAINING_TITLE)
                .where(AttendanceSession.opens_at < oldest)
            )
        )
        .scalars()
        .first()
    )
    if already is not None:
        print("Attendance already seeded, skipping.")
        return []

    records: list[AttendanceRecord] = []
    sessions_created = 0
    for day in dates:
        opens = datetime(day.year, day.month, day.day, 18, 0, tzinfo=UTC)
        row = AttendanceSession(
            tenant_id=tenant.id,
            title=TRAINING_TITLE,
            location="Schießstand Vereinsheim",
            opens_at=opens,
            closes_at=opens + timedelta(hours=4),
            status="open",
            supervisor_member_id=rng.choice(supervisors).id,
            created_by=user.id,
            updated_by=user.id,
        )
        session.add(row)
        await session.flush()
        sessions_created += 1

        present = rng.sample(active, k=max(3, int(len(active) * ATTENDANCE_SHARE)))
        for member in present:
            # Scanned or ticked off by hand — the two ways a club evening
            # actually fills, with the assurance each earns.
            scanned = rng.random() < 0.6
            checked_in = opens + timedelta(minutes=rng.randint(0, 90))
            record = AttendanceRecord(
                tenant_id=tenant.id,
                session_id=row.id,
                origin="club",
                member_id=member.id,
                occurred_on=day,
                checked_in_at=checked_in,
                checked_out_at=checked_in + timedelta(minutes=rng.randint(60, 150)),
                method="staff_scan" if scanned else "manual",
                assurance="high" if scanned else "low",
                verified_by_user_id=user.id,
                created_by=user.id,
                updated_by=user.id,
            )
            session.add(record)
            records.append(record)
        await session.flush()

        if day < today:
            row.status = "closed"
            row.closed_at = row.closes_at
            row.closed_by = user.id
            live = [r for r in records if r.session_id == row.id]
            row.close_hash = session_close_hash(row.id, live)
            await session.flush()
            await append_entry(
                session,
                tenant.id,
                entry_type="session_close",
                subject_id=row.id,
                content_hash=row.close_hash,
            )

    print(f"Created {sessions_created} training sessions with {len(records)} check-ins.")
    return records


async def _ensure_self_entries(
    session: AsyncSession,
    tenant: Tenant,
    user: User,
    members: list[Member],
    rng: random.Random,
) -> None:
    """Self-kept range days: someone else's range, and one's own.

    Both are unsupervised and both say so — method `self`, assurance `low`.
    The second kind has no location at all, which is the case a member
    shooting alone on the club's range falls into.
    """
    existing = (
        (
            await session.execute(
                select(AttendanceRecord)
                .where(AttendanceRecord.tenant_id == tenant.id)
                .where(AttendanceRecord.origin == "external")
                .where(AttendanceRecord.deleted_at.is_(None))
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        print("Self-kept entries already seeded, skipping.")
        return

    today = datetime.now(UTC).date()
    active = [m for m in members if m.status == "active"]
    created = 0
    for member in rng.sample(active, k=min(6, len(active))):
        for _ in range(rng.randint(1, 3)):
            day = today - timedelta(days=rng.randint(3, 25))
            foreign = rng.random() < 0.6
            session.add(
                AttendanceRecord(
                    tenant_id=tenant.id,
                    session_id=None,
                    origin="external",
                    external_location=(rng.choice(FOREIGN_RANGES) if foreign else None),
                    member_id=member.id,
                    occurred_on=day,
                    checked_in_at=datetime(day.year, day.month, day.day, 17, 30, tzinfo=UTC),
                    method="self",
                    assurance="low",
                    note=None if foreign else "Allein auf dem Vereinsstand",
                    created_by=user.id,
                    updated_by=user.id,
                )
            )
            created += 1
    # One row per member and day is a database rule, so a duplicate draw has to
    # be flushed away rather than fought over.
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        print("Self-kept entries collided on a day, skipping them.")
        return
    print(f"Created {created} self-kept range days.")


async def _ensure_shooting_details(
    session: AsyncSession,
    tenant: Tenant,
    records: list[AttendanceRecord],
    rng: random.Random,
) -> None:
    """What each person shot that evening — the range book's own columns."""
    if not records:
        print("No new attendance records, skipping shooting details.")
        return

    club_disciplines = (
        (await session.execute(select(ClubDiscipline).where(ClubDiscipline.tenant_id == tenant.id)))
        .scalars()
        .all()
    )
    by_name = {d.name: d for d in club_disciplines}

    created = 0
    for record in records:
        # Not every row gets one: a supervisor filling in twenty people misses
        # some, and the proof has to survive that.
        if rng.random() < 0.12:
            continue
        name = rng.choice(list(TARGET_BY_DISCIPLINE))
        discipline = by_name.get(name)
        session.add(
            ShootingRecordDetail(
                tenant_id=tenant.id,
                attendance_record_id=record.id,
                club_discipline_id=discipline.id if discipline else None,
                weapon_category=WEAPON_BY_DISCIPLINE.get(name, rng.choice(WEAPON_CATEGORIES)),
                rounds_fired=rng.choice((20, 30, 40, 50, 60)),
            )
        )
        created += 1
    await session.flush()
    print(f"Created {created} shooting record details.")


async def _ensure_shot_series(
    session: AsyncSession,
    tenant: Tenant,
    user: User,
    members: list[Member],
    rng: random.Random,
) -> None:
    """Recorded series with real holes in them.

    Scored through `score_series`, the same engine the API runs, so every ring,
    inner ten and grouping in the seed is one the server would have computed
    for those coordinates.
    """
    target_rows = (await session.execute(select(TargetType))).scalars().all()
    geometries = {row.slug: TargetGeometry.from_model(row) for row in target_rows}
    if not geometries:
        print("No target types in the catalog, skipping shot series.")
        return

    free_training = (
        await session.execute(
            select(Competition)
            .where(Competition.tenant_id == tenant.id)
            .where(Competition.competition_type == FREE_TRAINING_TYPE)
        )
    ).scalar_one_or_none()
    if free_training is None:
        free_training = Competition(
            tenant_id=tenant.id,
            name=FREE_TRAINING_NAME,
            competition_type=FREE_TRAINING_TYPE,
            start_date=datetime.now(UTC).date() - timedelta(days=365),
            scoring_mode="highest_wins",
            scoring_unit="Ringe",
        )
        session.add(free_training)
        await session.flush()

    # Counted, not merely detected: a handful of series recorded by hand while
    # testing must not stand in for a seeded history.
    recorded = (
        await session.execute(
            select(func.count())
            .select_from(Entry)
            .where(Entry.tenant_id == tenant.id)
            .where(Entry.details.is_not(None))
            .where(Entry.deleted_at.is_(None))
        )
    ).scalar_one()
    if recorded >= SEEDED_SERIES_MARKER:
        print("Shot series already seeded, skipping.")
        return

    today = datetime.now(UTC).date()
    active = [m for m in members if m.status == "active"]
    shooters = rng.sample(active, k=min(10, len(active)))
    series = 0
    for member in shooters:
        # A steady shooter and an erratic one look different on paper, and the
        # history screen is only worth looking at if they do.
        skill = rng.uniform(0.35, 0.95)
        for _ in range(rng.randint(2, 6)):
            day = today - timedelta(days=rng.randint(1, 120))
            name = rng.choice(list(TARGET_BY_DISCIPLINE))
            geometry = geometries.get(TARGET_BY_DISCIPLINE[name])
            if geometry is None:
                continue

            round_session = (
                await session.execute(
                    select(Session)
                    .where(Session.competition_id == free_training.id)
                    .where(Session.date == day)
                    .where(Session.discipline == name)
                )
            ).scalar_one_or_none()
            if round_session is None:
                round_session = Session(
                    tenant_id=tenant.id,
                    competition_id=free_training.id,
                    name=FREE_TRAINING_NAME,
                    date=day,
                    discipline=name,
                )
                session.add(round_session)
                await session.flush()

            shots = _shots_for(rng, geometry, rng.choice((5, 10)), skill)
            scored = score_series(shots, geometry)
            session.add(
                Entry(
                    tenant_id=tenant.id,
                    session_id=round_session.id,
                    member_id=member.id,
                    score_value=scored.total,
                    score_unit="Ringe",
                    discipline=name,
                    details={
                        "shots": [
                            {
                                "x": round(s.x, 4),
                                "y": round(s.y, 4),
                                "ring": s.ring,
                                "inner_ten": s.inner_ten,
                                "caliber_mm": s.caliber_mm,
                                "source": "manual",
                            }
                            for s in scored.shots
                        ],
                        "target_type": geometry.slug,
                        "caliber_mm": geometry.default_caliber_mm,
                        "inner_tens": scored.inner_tens,
                        "grouping_mm": scored.grouping_mm,
                    },
                    source="manual",
                    recorded_by=user.id,
                    recorded_at=datetime(day.year, day.month, day.day, 19, 0, tzinfo=UTC),
                    created_by=user.id,
                    updated_by=user.id,
                )
            )
            series += 1
    await session.flush()
    print(f"Created {series} recorded shot series.")


async def _ensure_proof_rules(session: AsyncSession, tenant: Tenant, user: User) -> None:
    """The §14 thresholds, as configuration rather than code."""
    existing = (
        (
            await session.execute(
                select(ShootingProofRule).where(ShootingProofRule.tenant_id == tenant.id)
            )
        )
        .scalars()
        .all()
    )
    if existing:
        print("Proof rules already seeded, skipping.")
        return

    for rule in (
        ShootingProofRule(
            tenant_id=tenant.id,
            rule_key="waffg-14-regel",
            label="§14 WaffG — Regelnachweis",
            window_months=12,
            min_total_days=18,
            min_distinct_months=12,
            created_by=user.id,
            updated_by=user.id,
        ),
        ShootingProofRule(
            tenant_id=tenant.id,
            rule_key="waffg-14-bedarf",
            label="§14 WaffG — Bedürfnisprüfung",
            window_months=12,
            min_total_days=12,
            created_by=user.id,
            updated_by=user.id,
        ),
    ):
        session.add(rule)
    await session.flush()
    print("Created 2 proof rules.")


async def _ensure_certificates(
    session: AsyncSession,
    tenant: Tenant,
    user: User,
    members: list[Member],
) -> None:
    """Issued proofs, through the service that issues real ones.

    Not hand-built rows: the certificate carries a content hash over the days
    it rests on and a verification code that the public check page resolves.
    Faking either would give the seed a document that cannot be verified —
    exactly the thing the feature exists to prevent.
    """
    existing = (
        (
            await session.execute(
                select(ShootingProofCertificate).where(
                    ShootingProofCertificate.tenant_id == tenant.id
                )
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        print("Certificates already seeded, skipping.")
        return

    service = ShootingService(
        session, AuthContext(user_id=user.id, tenant_id=tenant.id, role="owner")
    )
    # Evaluated first, issued only where it passes. Issuing regardless would
    # produce documents reading "failed, 0 days" — a state the club can reach,
    # but useless as sample data and misleading on a screen.
    issued = 0
    for member in members:
        if issued >= 3:
            break
        evaluation = await service.evaluate(member.id, "waffg-14-regel")
        if not evaluation.get("passed"):
            continue
        await service.issue_certificate(
            CertificateIssue(member_id=member.id, rule_key="waffg-14-regel")
        )
        issued += 1
    await session.flush()
    print(f"Issued {issued} certificates.")


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
        records = await _ensure_attendance(session, tenant, user, members, rng)
        await _ensure_self_entries(session, tenant, user, members, rng)
        await _ensure_shooting_details(session, tenant, records, rng)
        await _ensure_shot_series(session, tenant, user, members, rng)
        await _ensure_proof_rules(session, tenant, user)
        await _ensure_certificates(session, tenant, user, members)
        await session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
