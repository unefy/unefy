"""The round mail: queueing, sending, and getting out again.

Sending is the one thing in this product that cannot be undone. So the tests
here are less about features than about promises: nobody is written to twice,
a restart in the middle changes nothing, one bad address does not stop the
other two hundred, and a member who unsubscribes is out.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.unsubscribe import sign, verify
from app.models.consent import MemberConsent
from app.models.member import Member
from app.models.message import EmailMessage, EmailRecipient
from app.models.tenant import Tenant
from app.models.user import TenantMembership, User
from app.schemas.message import AllMembers
from app.services.message import MessageService
from app.tasks.mail_queue import message_progress, send_batch

BASE = "/api/v1/messages"


def sending_settings(**overrides: object) -> Settings:
    """A club that is allowed to send, with tiny batches so a test can watch
    the loop take two rounds."""
    base: dict[str, object] = {
        "DEBUG": True,
        "EMAIL_DELIVERY": "all",
        "SMTP_HOST": "mail.example.org",
        "EMAIL_BATCH_SIZE": 2,
        "EMAIL_MAX_ATTEMPTS": 2,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type, call-arg]


class Postbox:
    """Stands in for the mail server; can be told to refuse an address."""

    def __init__(self, refuse: set[str] | None = None) -> None:
        self.sent: list[tuple[str, str]] = []
        self.refuse = refuse or set()

    async def __call__(self, message: object, **_: object) -> None:
        to = str(message["To"])  # type: ignore[index]
        if to in self.refuse:
            raise OSError("mailbox unavailable")
        self.sent.append((to, str(message["Subject"])))  # type: ignore[index]

    @property
    def addresses(self) -> list[str]:
        return [to for to, _ in self.sent]


@pytest.fixture
def postbox(monkeypatch: pytest.MonkeyPatch) -> Postbox:
    box = Postbox()
    monkeypatch.setattr("app.integrations.email.aiosmtplib.send", box)
    return box


async def a_member(
    db_session: AsyncSession,
    tenant: Tenant,
    user: User,
    *,
    number: str,
    email: str | None,
    last_name: str = "Weber",
) -> Member:
    member = Member(
        tenant_id=tenant.id,
        member_number=number,
        first_name="Jonas",
        last_name=last_name,
        email=email,
        joined_at=date(2020, 1, 1),
        status="active",
        created_by=user.id,
        updated_by=user.id,
    )
    db_session.add(member)
    await db_session.flush()
    return member


def auth_for(user: User, tenant: Tenant, role: str = "owner"):  # type: ignore[no-untyped-def]
    from app.dependencies import AuthContext

    return AuthContext(user_id=user.id, tenant_id=tenant.id, role=role)


async def queue_one(
    db_session: AsyncSession,
    tenant: Tenant,
    user: User,
    *,
    kind: str = "notice",
    settings: Settings | None = None,
) -> EmailMessage:
    service = MessageService(db_session, auth_for(user, tenant))
    return await service.queue(
        kind=kind,  # type: ignore[arg-type]
        subject="Einladung zur Mitgliederversammlung",
        body="Am 14. März um 19 Uhr im Vereinsheim.",
        audience=AllMembers(),
        settings=settings or sending_settings(),
    )


# --- Clients for the roles this module distinguishes ---


async def _client_for(
    db_session: AsyncSession,
    fake_redis: Any,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
) -> AsyncGenerator[AsyncClient]:
    import json

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
        transport=ASGITransport(app=app), base_url="http://test", cookies={"unefy_session": token}
    ) as client:
        yield client

    redis_module._redis_client = original_redis


@pytest.fixture
def sending(request: pytest.FixtureRequest) -> None:
    """Let the endpoints send: the app's own settings default to `auth_only`,
    which is the right default and would otherwise refuse every message."""
    from app.config import get_settings
    from app.main import app

    # A plain lambda, not `sending_settings` itself: FastAPI reads the
    # override's signature, and `**overrides` would become a request
    # parameter it then rejects the body over.
    app.dependency_overrides[get_settings] = lambda: sending_settings()
    request.addfinalizer(lambda: app.dependency_overrides.pop(get_settings, None))


@pytest.fixture
async def member_client(
    db_session: AsyncSession, fake_redis: Any, test_tenant: Tenant
) -> AsyncGenerator[AsyncClient]:
    user = User(id=uuid.uuid4(), email="mitglied@example.org", name="Mitglied")
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
    tenant = Tenant(id=uuid.uuid4(), name="Nachbarverein", slug="nachbar-post")
    user = User(id=uuid.uuid4(), email="vorstand@nachbar.example", name="Nachbar")
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


# --- Queueing freezes the list ---


async def test_queueing_writes_one_row_per_member(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    await a_member(db_session, test_tenant, test_user, number="001", email="a@example.org")
    await a_member(db_session, test_tenant, test_user, number="002", email="b@example.org")

    message = await queue_one(db_session, test_tenant, test_user)

    assert message.recipient_count == 2
    assert message.status == "queued"
    assert await message_progress(db_session, message.id) == {"pending": 2}


async def test_one_mailbox_gets_one_mail(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """A couple sharing an address is one inbox — but both stay in the record,
    so "did Erika get it" has an answer."""
    await a_member(db_session, test_tenant, test_user, number="001", email="haushalt@example.org")
    await a_member(db_session, test_tenant, test_user, number="002", email="Haushalt@Example.org")

    message = await queue_one(db_session, test_tenant, test_user)

    progress = await message_progress(db_session, message.id)
    assert progress == {"pending": 1, "skipped": 1}
    duplicate = (
        await db_session.execute(
            select(EmailRecipient)
            .where(EmailRecipient.message_id == message.id)
            .where(EmailRecipient.status == "skipped")
        )
    ).scalar_one()
    assert duplicate.reason == "duplicate"


async def test_a_message_that_reaches_nobody_is_refused(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """Otherwise the club goes looking for a mail that never existed."""
    from app.core.exceptions import ValidationError

    await a_member(db_session, test_tenant, test_user, number="001", email=None)

    with pytest.raises(ValidationError):
        await queue_one(db_session, test_tenant, test_user)


async def test_the_selection_is_stored_not_its_result(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    await a_member(db_session, test_tenant, test_user, number="001", email="a@example.org")

    message = await queue_one(db_session, test_tenant, test_user)

    assert message.audience == {"type": "all"}


# --- Sending ---


async def test_the_loop_works_through_the_batches(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User, postbox: Postbox
) -> None:
    for index in range(3):
        await a_member(
            db_session, test_tenant, test_user, number=f"00{index}", email=f"m{index}@example.org"
        )
    settings = sending_settings()
    message = await queue_one(db_session, test_tenant, test_user, settings=settings)

    first = await send_batch(db_session, settings)
    second = await send_batch(db_session, settings)

    assert (first, second) == (2, 1), "the batch size is meant to be respected"
    assert sorted(postbox.addresses) == ["m0@example.org", "m1@example.org", "m2@example.org"]
    await db_session.refresh(message)
    assert message.status == "sent"
    assert message.finished_at is not None


async def test_nobody_is_written_to_twice(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User, postbox: Postbox
) -> None:
    """The promise with no undo behind it. A second run over a finished
    message must be a no-op, not a second invitation."""
    await a_member(db_session, test_tenant, test_user, number="001", email="a@example.org")
    settings = sending_settings()
    await queue_one(db_session, test_tenant, test_user, settings=settings)

    await send_batch(db_session, settings)
    await send_batch(db_session, settings)
    await send_batch(db_session, settings)

    assert postbox.addresses == ["a@example.org"]


async def test_a_restart_in_the_middle_carries_on(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User, postbox: Postbox
) -> None:
    """Progress lives in the rows, so the process may die between batches."""
    for index in range(4):
        await a_member(
            db_session, test_tenant, test_user, number=f"00{index}", email=f"m{index}@example.org"
        )
    settings = sending_settings()
    message = await queue_one(db_session, test_tenant, test_user, settings=settings)

    await send_batch(db_session, settings)
    assert len(postbox.addresses) == 2
    # …the backend is killed here. Nothing in memory survives; the rows do.
    db_session.expire_all()

    await send_batch(db_session, settings)
    await send_batch(db_session, settings)

    assert len(postbox.addresses) == 4
    assert len(set(postbox.addresses)) == 4, "somebody was written to twice"
    await db_session.refresh(message)
    assert message.status == "sent"


async def test_one_bad_address_does_not_stop_the_rest(
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
    postbox: Postbox,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    postbox.refuse = {"kaputt@example.org"}
    await a_member(db_session, test_tenant, test_user, number="001", email="kaputt@example.org")
    await a_member(db_session, test_tenant, test_user, number="002", email="gut@example.org")
    settings = sending_settings()
    message = await queue_one(db_session, test_tenant, test_user, settings=settings)

    await send_batch(db_session, settings)
    await send_batch(db_session, settings)  # the retry, which fails again

    assert postbox.addresses == ["gut@example.org"]
    rows = {
        r.email: r
        for r in (
            await db_session.execute(
                select(EmailRecipient).where(EmailRecipient.message_id == message.id)
            )
        )
        .scalars()
        .all()
    }
    assert rows["gut@example.org"].status == "sent"
    assert rows["kaputt@example.org"].status == "failed"
    assert rows["kaputt@example.org"].error
    await db_session.refresh(message)
    # Two hundred sent and three refused is not a failed mailing.
    assert message.status == "sent"


async def test_a_failure_is_retried_before_it_is_given_up_on(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User, postbox: Postbox
) -> None:
    postbox.refuse = {"kaputt@example.org"}
    await a_member(db_session, test_tenant, test_user, number="001", email="kaputt@example.org")
    settings = sending_settings(EMAIL_MAX_ATTEMPTS=3)
    message = await queue_one(db_session, test_tenant, test_user, settings=settings)

    await send_batch(db_session, settings)
    row = (
        await db_session.execute(
            select(EmailRecipient).where(EmailRecipient.message_id == message.id)
        )
    ).scalar_one()
    assert (row.status, row.attempts) == ("pending", 1)

    await send_batch(db_session, settings)
    await send_batch(db_session, settings)
    await db_session.refresh(row)

    assert (row.status, row.attempts) == ("failed", 3)


async def test_a_mailing_where_everything_failed_says_so(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User, postbox: Postbox
) -> None:
    postbox.refuse = {"kaputt@example.org"}
    await a_member(db_session, test_tenant, test_user, number="001", email="kaputt@example.org")
    settings = sending_settings(EMAIL_MAX_ATTEMPTS=1)
    message = await queue_one(db_session, test_tenant, test_user, settings=settings)

    await send_batch(db_session, settings)

    await db_session.refresh(message)
    assert message.status == "failed"


async def test_a_held_back_installation_sends_nothing_and_says_why(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User, postbox: Postbox
) -> None:
    """The switch from the delivery guard, seen from the round mail: the rows
    are skipped with a reason, not failed, and the board is told before it
    presses send."""
    from app.core.exceptions import AppError

    await a_member(db_session, test_tenant, test_user, number="001", email="a@example.org")
    settings = sending_settings(EMAIL_DELIVERY="auth_only")

    with pytest.raises(AppError) as refused:
        await queue_one(db_session, test_tenant, test_user, settings=settings)

    # Named, because "reaches nobody" would send the board looking through
    # consents for a setting.
    assert refused.value.code == "EMAIL_HELD_BACK"
    assert postbox.sent == []


async def test_flipping_the_switch_mid_mailing_stops_the_rest(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User, postbox: Postbox
) -> None:
    """The delivery switch holds even for a message that is already going out.

    The realistic shape of the accident this guards: somebody notices mid-send
    that real members are being written to and flips `EMAIL_DELIVERY`. What is
    gone is gone — but the rest must stop, and must not be recorded as sent.
    """
    for index in range(4):
        await a_member(
            db_session, test_tenant, test_user, number=f"00{index}", email=f"m{index}@example.org"
        )
    settings = sending_settings()
    message = await queue_one(db_session, test_tenant, test_user, settings=settings)

    await send_batch(db_session, settings)
    assert len(postbox.addresses) == 2

    held = sending_settings(EMAIL_DELIVERY="auth_only")
    await send_batch(db_session, held)

    assert len(postbox.addresses) == 2, "the switch was flipped and mail still went out"
    rows = (
        (
            await db_session.execute(
                select(EmailRecipient)
                .where(EmailRecipient.message_id == message.id)
                .where(EmailRecipient.status == "skipped")
            )
        )
        .scalars()
        .all()
    )
    assert [r.reason for r in rows] == ["held_back", "held_back"]
    await db_session.refresh(message)
    # Two of four left; that is not a failed mailing and not a complete one
    # either — the rows say which is which.
    assert message.status == "sent"


async def test_the_preview_counts_what_the_send_would_do(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    await a_member(db_session, test_tenant, test_user, number="001", email="a@example.org")
    await a_member(db_session, test_tenant, test_user, number="002", email=None)
    settings = sending_settings()

    summary, _ = await MessageService(db_session, auth_for(test_user, test_tenant)).preview(
        AllMembers(), "notice", settings=settings
    )

    assert (summary.total, summary.pending, summary.skipped_no_email) == (2, 1, 1)


async def test_a_newsletter_only_reaches_those_who_agreed(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User, postbox: Postbox
) -> None:
    yes = await a_member(db_session, test_tenant, test_user, number="001", email="ja@example.org")
    await a_member(db_session, test_tenant, test_user, number="002", email="nie@example.org")
    db_session.add(
        MemberConsent(
            tenant_id=test_tenant.id,
            member_id=yes.id,
            kind="newsletter",
            granted=True,
            recorded_at=datetime.now(UTC),
            source="self",
        )
    )
    await db_session.flush()
    settings = sending_settings()

    await queue_one(db_session, test_tenant, test_user, kind="newsletter", settings=settings)
    await send_batch(db_session, settings)

    assert postbox.addresses == ["ja@example.org"]


# --- Getting out again ---


def test_an_unsubscribe_token_survives_a_round_trip() -> None:
    member_id = uuid.uuid4()

    assert verify(sign(member_id, "secret"), "secret") == member_id


@pytest.mark.parametrize(
    "token",
    ["", "nonsense", "not-a-uuid.abcdef", "{member}.deadbeefdeadbeef", "{member}"],
)
def test_a_tampered_token_names_nobody(token: str) -> None:
    member_id = uuid.uuid4()

    assert verify(token.format(member=member_id), "secret") is None


def test_a_token_from_another_secret_does_not_hold(monkeypatch: pytest.MonkeyPatch) -> None:
    member_id = uuid.uuid4()

    assert verify(sign(member_id, "one"), "two") is None


async def test_the_link_takes_a_member_off_the_list(
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
    anon_client: AsyncClient,
    postbox: Postbox,
) -> None:
    """End to end: the member unsubscribes without signing in, and the next
    newsletter skips them."""
    settings = get_settings()
    member = await a_member(
        db_session, test_tenant, test_user, number="001", email="raus@example.org"
    )
    db_session.add(
        MemberConsent(
            tenant_id=test_tenant.id,
            member_id=member.id,
            kind="newsletter",
            granted=True,
            recorded_at=datetime.now(UTC),
            source="self",
        )
    )
    await db_session.flush()
    token = sign(member.id, settings.SESSION_SECRET)

    shown = await anon_client.get(f"/unsubscribe/{token}")
    assert shown.status_code == 200
    assert shown.json()["data"]["email"] == "raus@example.org"

    done = await anon_client.post(f"/unsubscribe/{token}")
    assert done.status_code == 200

    summary, _ = await MessageService(db_session, auth_for(test_user, test_tenant)).preview(
        AllMembers(), "newsletter", settings=sending_settings()
    )
    assert (summary.pending, summary.skipped_refused) == (0, 1)


async def test_opening_the_link_does_not_unsubscribe_anybody(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User, anon_client: AsyncClient
) -> None:
    """Mail clients and scanners follow links in the background. A GET that
    unsubscribed would take people off the list who never clicked."""
    settings = get_settings()
    member = await a_member(
        db_session, test_tenant, test_user, number="001", email="raus@example.org"
    )

    await anon_client.get(f"/unsubscribe/{sign(member.id, settings.SESSION_SECRET)}")

    entries = (
        (
            await db_session.execute(
                select(MemberConsent).where(MemberConsent.member_id == member.id)
            )
        )
        .scalars()
        .all()
    )
    assert entries == []


async def test_an_invalid_link_says_so_rather_than_guessing(anon_client: AsyncClient) -> None:
    response = await anon_client.post(f"/unsubscribe/{uuid.uuid4()}.deadbeefdeadbeef")

    assert response.status_code == 404


async def test_a_newsletter_carries_a_way_out(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """In the text and in `List-Unsubscribe` — without the header the
    unsubscribe button disappears from Gmail and people press "spam" instead."""
    from app.tasks.mail_queue import _for_recipient

    member = await a_member(db_session, test_tenant, test_user, number="001", email="a@example.org")
    db_session.add(
        MemberConsent(
            tenant_id=test_tenant.id,
            member_id=member.id,
            kind="newsletter",
            granted=True,
            recorded_at=datetime.now(UTC),
            source="self",
        )
    )
    await db_session.flush()
    settings = sending_settings()
    message = await queue_one(
        db_session, test_tenant, test_user, kind="newsletter", settings=settings
    )
    recipient = (
        await db_session.execute(
            select(EmailRecipient).where(EmailRecipient.message_id == message.id)
        )
    ).scalar_one()

    body, headers = _for_recipient(message, recipient, settings)

    assert "Abmelden: " in body
    assert sign(member.id, settings.SESSION_SECRET) in body
    assert headers["List-Unsubscribe"].startswith("<")
    assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


async def test_a_duty_notice_carries_none(
    db_session: AsyncSession, test_tenant: Tenant, test_user: User
) -> None:
    """There is nothing to unsubscribe from, and offering it would promise
    something the club cannot keep."""
    from app.tasks.mail_queue import _for_recipient

    await a_member(db_session, test_tenant, test_user, number="001", email="a@example.org")
    settings = sending_settings()
    message = await queue_one(db_session, test_tenant, test_user, settings=settings)
    recipient = (
        await db_session.execute(
            select(EmailRecipient).where(EmailRecipient.message_id == message.id)
        )
    ).scalar_one()

    body, headers = _for_recipient(message, recipient, settings)

    assert body == message.body
    assert headers == {}


# --- The endpoints ---


async def test_a_member_may_not_send_to_the_club(member_client: AsyncClient) -> None:
    """Round mail is board work end to end — including reading the history."""
    assert (await member_client.get(BASE)).status_code == 403
    assert (
        await member_client.post(
            BASE,
            json={
                "kind": "notice",
                "subject": "Einladung",
                "body": "Am 14. März.",
                "audience": {"type": "all"},
            },
        )
    ).status_code == 403


async def test_the_endpoints_refuse_an_anonymous_caller(anon_client: AsyncClient) -> None:
    assert (await anon_client.get(BASE)).status_code == 403
    assert (
        await anon_client.post(
            f"{BASE}/preview", json={"kind": "notice", "audience": {"type": "all"}}
        )
    ).status_code == 403


async def test_queueing_through_the_api_and_reading_it_back(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
    sending: None,
) -> None:
    await a_member(db_session, test_tenant, test_user, number="001", email="a@example.org")

    preview = await auth_client.post(
        f"{BASE}/preview", json={"kind": "notice", "audience": {"type": "all"}}
    )
    assert preview.status_code == 200
    assert preview.json()["data"]["summary"]["total"] == 1

    created = await auth_client.post(
        BASE,
        json={
            "kind": "notice",
            "subject": "Einladung",
            "body": "Am 14. März.",
            "audience": {"type": "all"},
        },
    )
    assert created.status_code == 201, created.text

    message_id = created.json()["data"]["id"]

    listing = await auth_client.get(BASE)
    assert [m["id"] for m in listing.json()["data"]] == [message_id]

    recipients = await auth_client.get(f"{BASE}/{message_id}/recipients")
    assert [r["email"] for r in recipients.json()["data"]] == ["a@example.org"]


async def test_another_club_cannot_read_this_ones_mailings(
    auth_client: AsyncClient,
    other_club_client: AsyncClient,
    db_session: AsyncSession,
    test_tenant: Tenant,
    test_user: User,
    sending: None,
) -> None:
    await a_member(db_session, test_tenant, test_user, number="001", email="a@example.org")
    created = await auth_client.post(
        BASE,
        json={
            "kind": "notice",
            "subject": "Einladung",
            "body": "Am 14. März.",
            "audience": {"type": "all"},
        },
    )
    message_id = created.json()["data"]["id"]

    assert (await other_club_client.get(BASE)).json()["data"] == []
    assert (await other_club_client.get(f"{BASE}/{message_id}")).status_code == 404
    assert (await other_club_client.get(f"{BASE}/{message_id}/recipients")).status_code == 404
