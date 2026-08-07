"""Tests for POST /api/v1/entries and GET /api/v1/entries/me.

Two behaviours carry this endpoint and both are covered here: it resolves its own
context (so a member alone on the range has somewhere to file a series), and it
recomputes every ring server-side (so two clients cannot disagree about a score).
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt import create_access_token
from app.core.target_type_seeds import TARGET_TYPES
from app.models.competition import Competition, Entry
from app.models.competition import Session as CompetitionSession
from app.models.member import Member
from app.models.target_type import TargetType
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from app.sync.cursor import CURSOR_SAFETY_LAG

RECORDED_AT = datetime(2026, 8, 5, 18, 30, tzinfo=UTC)
OCCURRED_ON = "2026-08-05"
#: The club's main target — 25 m precision, Scheibe Nr. 5.
TARGET = "sport_pistol_25m"


def _bearer(user: User, tenant: Tenant, role: str = "owner") -> dict[str, str]:
    token, _ = create_access_token(user_id=user.id, tenant_id=tenant.id, role=role)
    return {"Authorization": f"Bearer {token}"}


async def _as_role(session: AsyncSession, user: User, tenant: Tenant, role: str) -> dict[str, str]:
    """Give the user this role in the club and return matching bearer headers.

    The role in the JWT is not what authorises anything — `_resolve_bearer`
    re-reads `TenantMembership` on every request so a revoked role takes effect
    immediately. Tests therefore have to move the membership, not just the token.
    """
    existing = (
        await session.execute(
            select(TenantMembership)
            .where(TenantMembership.user_id == user.id)
            .where(TenantMembership.tenant_id == tenant.id)
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            TenantMembership(
                id=uuid.uuid4(),
                user_id=user.id,
                tenant_id=tenant.id,
                role=role,
                is_active=True,
            )
        )
    else:
        existing.role = role
        existing.is_active = True
    await session.flush()
    return _bearer(user, tenant, role)


async def _seed_target_types(session: AsyncSession) -> None:
    """The catalog is populated by a migration; tests build the schema with
    `create_all`, so it has to be inserted explicitly."""
    existing = set((await session.execute(select(TargetType.slug))).scalars().all())
    for entry in TARGET_TYPES:
        if entry["slug"] in existing:
            continue
        session.add(TargetType(id=uuid.uuid4(), **entry))
    await session.flush()


async def _seed_member(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    number: str = "001",
    name: str = "Max",
    user_id: uuid.UUID | None = None,
) -> Member:
    member = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_number=number,
        first_name=name,
        last_name="Test",
        joined_at=date(2024, 1, 1),
        status="active",
        user_id=user_id,
    )
    session.add(member)
    await session.flush()
    return member


def _payload(member_id: uuid.UUID, **overrides: object) -> dict:  # type: ignore[type-arg]
    body: dict = {  # type: ignore[type-arg]
        "member_id": str(member_id),
        "occurred_on": OCCURRED_ON,
        "discipline": "GK Pistole 25m",
        "target_type": TARGET,
        "caliber_mm": 9.0,
        "shots": [{"x": 0.0, "y": 0.0}],
        "source": "manual",
        "recorded_at": RECORDED_AT.isoformat(),
    }
    body.update(overrides)
    return body


# --- Context resolution ---


async def test_records_into_the_auto_created_free_training_series(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """No session_id: the club's "Freies Training" container appears on demand."""
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)

    resp = await auth_client.post(
        "/api/v1/entries",
        json=_payload(member.id),
        headers=_bearer(test_user, test_tenant),
    )
    assert resp.status_code == 201, resp.text

    competition = (
        await db_session.execute(
            select(Competition)
            .where(Competition.tenant_id == test_tenant.id)
            .where(Competition.competition_type == "free_training")
        )
    ).scalar_one()
    assert competition.name == "Freies Training"

    entry_session = (
        await db_session.execute(
            select(CompetitionSession).where(CompetitionSession.competition_id == competition.id)
        )
    ).scalar_one()
    assert entry_session.date == date(2026, 8, 5)
    assert entry_session.discipline == "GK Pistole 25m"


async def test_two_devices_same_day_share_one_session(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The session id is derived from club+day+discipline, so offline devices
    converge without coordinating."""
    await _seed_target_types(db_session)
    a = await _seed_member(db_session, test_tenant.id, number="001", name="Anna")
    b = await _seed_member(db_session, test_tenant.id, number="002", name="Bert")
    headers = _bearer(test_user, test_tenant)

    for member in (a, b):
        resp = await auth_client.post("/api/v1/entries", json=_payload(member.id), headers=headers)
        assert resp.status_code == 201, resp.text

    sessions = (
        (
            await db_session.execute(
                select(CompetitionSession).where(CompetitionSession.tenant_id == test_tenant.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(sessions) == 1

    entries = (
        (await db_session.execute(select(Entry).where(Entry.tenant_id == test_tenant.id)))
        .scalars()
        .all()
    )
    assert len(entries) == 2
    assert {e.session_id for e in entries} == {sessions[0].id}


async def test_different_disciplines_get_separate_sessions(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)
    headers = _bearer(test_user, test_tenant)

    for discipline in ("GK Pistole 25m", "KK Pistole 25m"):
        resp = await auth_client.post(
            "/api/v1/entries",
            json=_payload(member.id, discipline=discipline),
            headers=headers,
        )
        assert resp.status_code == 201, resp.text

    sessions = (
        (
            await db_session.execute(
                select(CompetitionSession).where(CompetitionSession.tenant_id == test_tenant.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(sessions) == 2


async def test_explicit_session_id_is_used(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)
    headers = _bearer(test_user, test_tenant)

    competition = Competition(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        name="Vereinsmeisterschaft",
        competition_type="competition",
        start_date=date(2026, 8, 1),
    )
    db_session.add(competition)
    await db_session.flush()
    comp_session = CompetitionSession(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        competition_id=competition.id,
        date=date(2026, 8, 5),
    )
    db_session.add(comp_session)
    await db_session.flush()

    resp = await auth_client.post(
        "/api/v1/entries",
        json=_payload(member.id, session_id=str(comp_session.id), occurred_on=None),
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["session_id"] == str(comp_session.id)

    # No free-training container was created for a competition entry.
    containers = (
        (
            await db_session.execute(
                select(Competition).where(Competition.competition_type == "free_training")
            )
        )
        .scalars()
        .all()
    )
    assert containers == []


async def test_unknown_session_is_rejected(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)

    resp = await auth_client.post(
        "/api/v1/entries",
        json=_payload(member.id, session_id=str(uuid.uuid4()), occurred_on=None),
        headers=_bearer(test_user, test_tenant),
    )
    assert resp.status_code == 404


async def test_neither_session_nor_date_is_rejected(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)

    resp = await auth_client.post(
        "/api/v1/entries",
        json=_payload(member.id, occurred_on=None),
        headers=_bearer(test_user, test_tenant),
    )
    assert resp.status_code == 422


# --- Scoring ---


async def test_server_recomputes_rings_and_ignores_the_clients_claim(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A client claiming a 10 for an obvious miss gets the server's answer."""
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)

    resp = await auth_client.post(
        "/api/v1/entries",
        json=_payload(
            member.id,
            shots=[{"x": 0.99, "y": 0.0, "ring": 10}],
        ),
        headers=_bearer(test_user, test_tenant),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["details"]["shots"][0]["ring"] == 1
    assert data["score_value"] == 1.0


async def test_score_value_is_the_sum_of_the_rings(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)

    resp = await auth_client.post(
        "/api/v1/entries",
        json=_payload(member.id, shots=[{"x": 0.0, "y": 0.0} for _ in range(5)]),
        headers=_bearer(test_user, test_tenant),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["score_value"] == 50.0
    assert data["details"]["inner_tens"] == 5
    assert data["score_unit"] == "Ringe"


async def test_two_calibres_on_one_sheet_score_differently(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The real case from the range: same position, .22 and 9 mm, different ring.

    Ring 10 has a 25 mm radius; the shot sits at 29 mm. A 9 mm bullet reaches
    24.5 mm and scores 10, a .22 reaches 26.2 mm and scores 9.
    """
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)
    # 29 mm as a fraction of the 250 mm scoring radius.
    position = 29.0 / 250.0

    resp = await auth_client.post(
        "/api/v1/entries",
        json=_payload(
            member.id,
            caliber_mm=9.0,
            shots=[
                {"x": position, "y": 0.0},
                {"x": position, "y": 0.0, "caliber_mm": 5.6},
            ],
        ),
        headers=_bearer(test_user, test_tenant),
    )
    assert resp.status_code == 201, resp.text
    shots = resp.json()["data"]["details"]["shots"]
    assert [s["ring"] for s in shots] == [10, 9]
    assert [s["caliber_mm"] for s in shots] == [9.0, 5.6]


async def test_unknown_target_type_is_rejected(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)

    resp = await auth_client.post(
        "/api/v1/entries",
        json=_payload(member.id, target_type="does_not_exist"),
        headers=_bearer(test_user, test_tenant),
    )
    assert resp.status_code == 422


# --- Idempotency ---


async def test_the_same_id_twice_creates_one_entry(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """What lets the offline queue retry without inventing duplicates."""
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)
    headers = _bearer(test_user, test_tenant)
    entry_id = str(uuid.uuid4())

    first = await auth_client.post(
        "/api/v1/entries", json=_payload(member.id, id=entry_id), headers=headers
    )
    second = await auth_client.post(
        "/api/v1/entries", json=_payload(member.id, id=entry_id), headers=headers
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["meta"]["created"] is True
    assert second.json()["meta"]["created"] is False

    entries = (
        (await db_session.execute(select(Entry).where(Entry.tenant_id == test_tenant.id)))
        .scalars()
        .all()
    )
    assert len(entries) == 1


# --- Roles ---


async def test_a_member_may_record_for_themselves(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id, user_id=test_user.id)
    headers = await _as_role(db_session, test_user, test_tenant, "member")

    resp = await client.post("/api/v1/entries", json=_payload(member.id), headers=headers)
    assert resp.status_code == 201, resp.text


async def test_a_member_may_not_record_for_someone_else(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await _seed_target_types(db_session)
    await _seed_member(db_session, test_tenant.id, number="001", user_id=test_user.id)
    other = await _seed_member(db_session, test_tenant.id, number="002", name="Other")
    headers = await _as_role(db_session, test_user, test_tenant, "member")

    resp = await client.post("/api/v1/entries", json=_payload(other.id), headers=headers)
    assert resp.status_code == 403


async def test_a_member_without_a_linked_record_may_not_record(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)
    headers = await _as_role(db_session, test_user, test_tenant, "member")

    resp = await client.post("/api/v1/entries", json=_payload(member.id), headers=headers)
    assert resp.status_code == 403


async def test_the_board_may_record_for_anyone(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)
    headers = await _as_role(db_session, test_user, test_tenant, "board")

    resp = await client.post("/api/v1/entries", json=_payload(member.id), headers=headers)
    assert resp.status_code == 201, resp.text


# --- /sync/entries: the board's club-wide view ---


async def test_sync_entries_returns_every_members_series_for_the_board(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The club view the app's "Verein" list is built on.

    Deliberately the mirror image of `/entries/me`: that route is hard-scoped to
    the caller, this one must return the series the caller had nothing to do
    with — otherwise a board member syncing the collection sees only their own
    bench and the club list is a slower copy of the personal one.
    """
    await _seed_target_types(db_session)
    mine = await _seed_member(db_session, test_tenant.id, number="001", user_id=test_user.id)
    other = await _seed_member(db_session, test_tenant.id, number="002", name="Other")
    headers = await _as_role(db_session, test_user, test_tenant, "board")

    resp = await client.post("/api/v1/entries", json=_payload(mine.id), headers=headers)
    assert resp.status_code == 201, resp.text

    db_session.add(
        Entry(
            tenant_id=test_tenant.id,
            session_id=(await db_session.execute(select(Entry.session_id))).scalars().first(),
            member_id=other.id,
            score_value=10,
            score_unit="rings",
            source="manual",
            # Somebody else entirely — neither the shooter nor the recorder is
            # the caller, which is exactly what `/entries/me` filters out.
            recorded_by=uuid.uuid4(),
            recorded_at=datetime.now(UTC),
        )
    )
    # Both rows carry `now()`, which sits *inside* the cursor's safety lag and
    # is therefore deliberately not served yet. Backdated rather than slept
    # through: the lag is five seconds, and the delay is what is under test in
    # test_sync.py, not here.
    behind_the_lag = datetime.now(UTC) - CURSOR_SAFETY_LAG - timedelta(minutes=1)
    await db_session.execute(update(Entry).values(updated_at=behind_the_lag))
    await db_session.commit()

    resp = await client.get("/api/v1/sync/entries", headers=headers)
    assert resp.status_code == 200, resp.text
    members = {row["member_id"] for row in resp.json()["data"]["changed"]}
    assert members == {str(mine.id), str(other.id)}


async def test_sync_entries_is_refused_for_a_plain_member(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """Which is what keeps every member's scores off every member's phone."""
    headers = await _as_role(db_session, test_user, test_tenant, "member")

    resp = await client.get("/api/v1/sync/entries", headers=headers)
    assert resp.status_code == 403


# --- /entries/me ---


async def test_me_returns_only_the_callers_own_entries(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await _seed_target_types(db_session)
    mine = await _seed_member(db_session, test_tenant.id, number="001", user_id=test_user.id)
    other = await _seed_member(db_session, test_tenant.id, number="002", name="Other")
    headers = await _as_role(db_session, test_user, test_tenant, "board")

    resp = await client.post("/api/v1/entries", json=_payload(mine.id), headers=headers)
    assert resp.status_code == 201, resp.text

    # Somebody else's series, entered by somebody else: neither half of the
    # scope matches, so it must not come back.
    db_session.add(
        Entry(
            tenant_id=test_tenant.id,
            session_id=(await db_session.execute(select(Entry.session_id))).scalars().first(),
            member_id=other.id,
            score_value=10,
            score_unit="rings",
            source="manual",
            recorded_by=uuid.uuid4(),
            recorded_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    resp = await client.get("/api/v1/entries/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["member_id"] == str(mine.id)


async def test_me_is_empty_without_a_linked_member_record(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """No member record is not an error — it is an empty history.

    It used to answer 404, which was wrong twice over: nothing is missing, and a
    board member with no member record of their own still has every series they
    entered for other people. That 404 hid all of them.
    """
    await _seed_target_types(db_session)
    headers = await _as_role(db_session, test_user, test_tenant, "member")
    resp = await client.get("/api/v1/entries/me", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == []
    assert resp.json()["meta"]["total"] == 0


# --- Isolation and list hygiene ---


async def test_free_training_is_hidden_from_the_competition_list(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The container is machinery. Left visible it would sit at the top of every
    club's competition screen forever, and cannot be deleted."""
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)
    headers = _bearer(test_user, test_tenant)

    await auth_client.post("/api/v1/entries", json=_payload(member.id), headers=headers)

    listing = await auth_client.get("/api/v1/competitions", headers=headers)
    assert listing.status_code == 200
    body = listing.json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0

    # Still reachable when asked for by name.
    explicit = await auth_client.get(
        "/api/v1/competitions?competition_type=free_training", headers=headers
    )
    assert len(explicit.json()["data"]) == 1


async def test_entries_are_tenant_scoped(
    client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    await _seed_target_types(db_session)
    other_tenant = Tenant(id=uuid.uuid4(), name="Other Club", slug="other-club")
    db_session.add(other_tenant)
    await db_session.flush()
    foreign_member = await _seed_member(db_session, other_tenant.id, number="999")

    headers = await _as_role(db_session, test_user, test_tenant, "board")
    resp = await client.post("/api/v1/entries", json=_payload(foreign_member.id), headers=headers)
    # `entries.member_id` has no tenant predicate of its own, so the service has
    # to check. Without it the row would carry this club's tenant_id and another
    # club's member_id.
    assert resp.status_code == 404


async def test_each_shot_keeps_where_it_came_from(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """One series holds both: what the photo detector found and what the
    shooter placed.

    Keeping the two apart per shot is what makes the detector measurable
    against real sheets — every recorded series becomes a comparison between
    what it proposed and what actually counted, without anyone annotating
    anything a second time.
    """
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)

    resp = await auth_client.post(
        "/api/v1/entries",
        json=_payload(
            member.id,
            shots=[
                {"x": 0.0, "y": 0.1, "source": "scan"},
                {"x": 0.2, "y": 0.0, "source": "manual"},
                {"x": -0.1, "y": 0.2},  # unsaid: falls back to the series
            ],
            source="scan",
        ),
        headers=_bearer(test_user, test_tenant),
    )
    assert resp.status_code == 201, resp.text

    entry = (
        await db_session.execute(select(Entry).where(Entry.member_id == member.id))
    ).scalar_one()
    assert [shot["source"] for shot in entry.details["shots"]] == ["scan", "manual", "scan"]


# --- Correcting a series ---


async def test_correcting_a_series_rescores_it_and_leaves_a_trace(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """A corrected series is scored by the same rules as a fresh one.

    And the correction is visible afterwards: a result that changed after the
    fact is a different thing from one that never did, which on a competition
    sheet is the difference between a record and an assertion.
    """
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)
    headers = _bearer(test_user, test_tenant)

    created = await auth_client.post(
        "/api/v1/entries",
        json=_payload(member.id, shots=[{"x": 0.0, "y": 0.0}]),
        headers=headers,
    )
    assert created.status_code == 201, created.text
    entry_id = created.json()["data"]["id"]

    # A shot the detector proposed was in the wrong place: move it out and add
    # one that was missed.
    corrected = await auth_client.patch(
        f"/api/v1/entries/{entry_id}",
        json={"shots": [{"x": 0.0, "y": 0.0}, {"x": 0.9, "y": 0.0, "source": "manual"}]},
        headers=headers,
    )
    assert corrected.status_code == 200, corrected.text

    await db_session.refresh(
        (await db_session.execute(select(Entry).where(Entry.id == entry_id))).scalar_one()
    )
    entry = (await db_session.execute(select(Entry).where(Entry.id == entry_id))).scalar_one()
    assert len(entry.details["shots"]) == 2
    assert entry.details["shots"][0]["ring"] == 10
    assert entry.details["shots"][1]["ring"] == 2
    assert float(entry.score_value) == 12.0

    edits = entry.details["edits"]
    assert len(edits) == 1
    assert edits[0]["previous_total"] == 10.0
    assert edits[0]["previous_shots"] == 1
    assert edits[0]["by"] == str(test_user.id)


async def test_a_member_cannot_correct_someone_elses_series(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The rule that guards recording guards correcting too."""
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)
    headers = _bearer(test_user, test_tenant)

    created = await auth_client.post("/api/v1/entries", json=_payload(member.id), headers=headers)
    entry_id = created.json()["data"]["id"]

    # As a plain member of the club — and with no member record of their own,
    # so this series is somebody else's.
    resp = await auth_client.patch(
        f"/api/v1/entries/{entry_id}",
        json={"shots": [{"x": 0.0, "y": 0.0}]},
        headers=await _as_role(db_session, test_user, test_tenant, "member"),
    )
    assert resp.status_code == 403, resp.text


async def test_a_series_recorded_for_someone_else_stays_visible(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The board sees what it entered, not only what it shot.

    `/entries/me` rebuilds the app's whole history list, so anything it leaves
    out disappears from the device once the queue has drained. Filtering on the
    caller's own member record alone hid nine of twelve real series — every one
    recorded for the shooter on the next bench.
    """
    await _seed_target_types(db_session)
    other = await _seed_member(db_session, test_tenant.id)
    headers = await _as_role(db_session, test_user, test_tenant, "board")

    created = await auth_client.post("/api/v1/entries", json=_payload(other.id), headers=headers)
    assert created.status_code == 201, created.text
    entry_id = created.json()["data"]["id"]

    listed = await auth_client.get("/api/v1/entries/me", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [e["id"] for e in listed.json()["data"]] == [entry_id]


async def test_deleting_a_series_withdraws_it_from_the_listing(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """Deleted is withdrawn, not erased — the row keeps its history."""
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)
    headers = await _as_role(db_session, test_user, test_tenant, "board")

    created = await auth_client.post("/api/v1/entries", json=_payload(member.id), headers=headers)
    entry_id = created.json()["data"]["id"]

    removed = await auth_client.delete(f"/api/v1/entries/{entry_id}", headers=headers)
    assert removed.status_code == 204, removed.text

    listed = await auth_client.get("/api/v1/entries/me", headers=headers)
    assert listed.json()["data"] == []

    # Still on the record, with a time of withdrawal.
    entry = (
        await db_session.execute(select(Entry).where(Entry.id == uuid.UUID(entry_id)))
    ).scalar_one()
    assert entry.deleted_at is not None

    # And gone for good as far as every route is concerned.
    again = await auth_client.delete(f"/api/v1/entries/{entry_id}", headers=headers)
    assert again.status_code == 404


async def test_a_member_cannot_delete_someone_elses_series(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
) -> None:
    """The rule that guards recording and correcting guards deleting too."""
    await _seed_target_types(db_session)
    member = await _seed_member(db_session, test_tenant.id)

    created = await auth_client.post(
        "/api/v1/entries", json=_payload(member.id), headers=_bearer(test_user, test_tenant)
    )
    entry_id = created.json()["data"]["id"]

    resp = await auth_client.delete(
        f"/api/v1/entries/{entry_id}",
        headers=await _as_role(db_session, test_user, test_tenant, "member"),
    )
    assert resp.status_code == 403, resp.text
