"""Delta sync.

Every test here corresponds to a way this design fails *silently*. That is the
selection criterion: a sync bug does not raise, it just leaves a row out, and the
symptom surfaces days later as "the app is missing a member" with nothing to
grep for. So the assertions are about completeness, not about status codes.

The invariant they collectively pin: **the delivered set is always a superset of
the changed set, never a subset.** Duplicates are free — a client applies every
row as an upsert by primary key. A missing row is unrecoverable.

One recurring device: rows are backdated with an explicit UPDATE before the
assertion. `func.now()` is Postgres's *transaction* timestamp, so everything
written inside one test transaction shares a single `updated_at`, and a test that
relies on time passing between two writes cannot fail. Backdating creates the
spread that production gets for free from separate requests.
"""

import base64
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.models.member import Member
from app.repositories.member import MemberRepository
from app.sync.cursor import CURSOR_MAX_AGE, CURSOR_SAFETY_LAG, encode_cursor, start_cursor

SYNC_MEMBERS = "/api/v1/sync/members"


async def _add_member(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    member_number: str,
    last_name: str = "Example",
) -> Member:
    member = Member(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_number=member_number,
        first_name="Alice",
        last_name=last_name,
        joined_at=date(2024, 1, 1),
        status="active",
    )
    session.add(member)
    await session.flush()
    return member


async def _set_updated_at(session: AsyncSession, member: Member, when: datetime) -> None:
    """Backdate a row so it sits in a known place in the keyset order."""
    await session.execute(update(Member).where(Member.id == member.id).values(updated_at=when))
    await session.flush()


async def _age_everything(
    session: AsyncSession, tenant_id: uuid.UUID, *, when: datetime | None = None
) -> datetime:
    """Push every member of a tenant safely behind the watermark.

    Rows written in this transaction carry `now()`, which is *newer* than
    `now() - CURSOR_SAFETY_LAG` and therefore invisible to sync. Production never
    has this problem — by the time anyone polls the write is seconds old — but a
    test has to create that gap deliberately. The same applies after a delete: a
    tombstone stamped `now()` is also too new to be served, which is a property of
    the watermark and not of the delete.
    """
    base = when or (datetime.now(UTC) - CURSOR_SAFETY_LAG - timedelta(minutes=5))
    await session.execute(
        update(Member).where(Member.tenant_id == tenant_id).values(updated_at=base)
    )
    await session.flush()
    return base


def _sync(body: dict[str, Any]) -> tuple[list[Any], list[Any], dict[str, Any]]:
    return body["data"]["changed"], body["data"]["deleted"], body["meta"]["sync"]


async def _drain(
    client: AsyncClient,
    url: str = SYNC_MEMBERS,
    *,
    limit: int = 200,
    cursor: str | None = None,
) -> tuple[list[Any], list[Any], str]:
    """Page until caught up, returning everything seen and the final cursor."""
    changed: list[Any] = []
    deleted: list[Any] = []
    for _ in range(50):  # a loop bound, so a paging bug fails instead of hanging
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        response = await client.get(url, params=params)
        assert response.status_code == 200, response.text
        page_changed, page_deleted, meta = _sync(response.json())
        changed.extend(page_changed)
        deleted.extend(page_deleted)
        cursor = meta["cursor"]
        if not meta["has_more"]:
            return changed, deleted, cursor
    raise AssertionError("sync never reported complete — paging does not converge")


class TestCompleteness:
    """Nothing may be skipped, whatever the timestamps look like."""

    async def test_rows_sharing_updated_at_all_arrive_exactly_once(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """The reason the cursor is a pair and not a bare timestamp.

        A bulk operation stamps many rows with one `updated_at`. A
        bare-timestamp cursor has to pick between `>` — which skips the siblings
        — and `>=`, which re-delivers them forever. Five identical timestamps
        drained one row at a time is the smallest case that tells those apart.
        """
        for i in range(5):
            await _add_member(db_session, test_tenant.id, member_number=f"{i:03d}")
        await _age_everything(db_session, test_tenant.id)

        changed, _deleted, _cursor = await _drain(auth_client, limit=1)

        ids = [row["id"] for row in changed]
        assert len(ids) == 5, f"expected all five, got {len(ids)}"
        assert len(set(ids)) == 5, "a row was delivered twice within one drain"

    async def test_a_row_changed_mid_drain_is_redelivered_not_skipped(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """Keyset paging can only push a row forward, never behind the cursor.

        This is the property offset pagination lacks: there, a concurrent write
        reshuffles the ordered set and a row slips between two pages unseen.
        """
        first = await _add_member(db_session, test_tenant.id, member_number="001")
        second = await _add_member(db_session, test_tenant.id, member_number="002")
        base = await _age_everything(db_session, test_tenant.id)
        await _set_updated_at(db_session, first, base)
        await _set_updated_at(db_session, second, base + timedelta(seconds=1))

        page = await auth_client.get(SYNC_MEMBERS, params={"limit": 1})
        changed, _deleted, meta = _sync(page.json())
        assert [row["id"] for row in changed] == [str(first.id)]
        assert meta["has_more"] is True

        # `first` is touched again, after the cursor now points past it.
        await _set_updated_at(db_session, first, base + timedelta(seconds=2))

        rest_changed, _rest_deleted, _cursor = await _drain(auth_client, limit=200)
        # Fresh drain from scratch would see both; what matters is that resuming
        # from the handed-out cursor still surfaces the re-touched row.
        resumed = await auth_client.get(
            SYNC_MEMBERS, params={"cursor": meta["cursor"], "limit": 200}
        )
        resumed_changed, _rd, _rm = _sync(resumed.json())
        resumed_ids = {row["id"] for row in resumed_changed}
        assert str(second.id) in resumed_ids
        assert str(first.id) in resumed_ids, (
            "a row updated after the cursor was issued was skipped — the delivered "
            "set must be a superset of the changed set"
        )
        assert rest_changed  # the full drain still works

    async def test_the_page_limit_is_respected(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        for i in range(7):
            await _add_member(db_session, test_tenant.id, member_number=f"{i:03d}")
        await _age_everything(db_session, test_tenant.id)

        response = await auth_client.get(SYNC_MEMBERS, params={"limit": 3})
        changed, _deleted, meta = _sync(response.json())
        assert len(changed) == 3
        assert meta["has_more"] is True


class TestTombstones:
    """A client has to learn about deletions, not infer them from absence."""

    async def test_a_soft_deleted_row_comes_back_as_a_tombstone(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        member = await _add_member(db_session, test_tenant.id, member_number="001")
        base = await _age_everything(db_session, test_tenant.id)

        _changed, _deleted, cursor = await _drain(auth_client)

        assert await MemberRepository(db_session, test_tenant.id).soft_delete(member.id)
        await _set_updated_at(db_session, member, base + timedelta(seconds=1))

        response = await auth_client.get(SYNC_MEMBERS, params={"cursor": cursor})
        changed, deleted, _meta = _sync(response.json())

        assert changed == []
        assert [row["id"] for row in deleted] == [str(member.id)]
        assert "last_name" not in deleted[0], (
            "a tombstone carried the row body — it must be id and time only, or "
            "deleted personal data gets broadcast to every device for two weeks"
        )

    async def test_a_bulk_soft_deleted_row_also_comes_back(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """The regression test for the trap that would have made this silent.

        `soft_delete_many` issues a Core UPDATE. Were `updated_at` left behind
        there, the tombstone would sort before every cursor already handed out and
        `POST /members/bulk-delete` would remove fifty members server-side while
        every phone kept showing all fifty. See `tests/test_repository_base.py`.
        """
        first = await _add_member(db_session, test_tenant.id, member_number="001")
        second = await _add_member(db_session, test_tenant.id, member_number="002")
        base = await _age_everything(db_session, test_tenant.id)

        _changed, _deleted, cursor = await _drain(auth_client)

        repo = MemberRepository(db_session, test_tenant.id)
        assert await repo.soft_delete_many([first.id, second.id]) == 2
        # Strictly after the cursor, and still behind the watermark. That the bulk
        # delete moves `updated_at` at all is pinned in test_repository_base.py;
        # what this test is about is the tombstone reaching the client.
        await _age_everything(db_session, test_tenant.id, when=base + timedelta(seconds=1))

        response = await auth_client.get(SYNC_MEMBERS, params={"cursor": cursor})
        _changed2, deleted, _meta = _sync(response.json())
        assert {row["id"] for row in deleted} == {str(first.id), str(second.id)}

    async def test_a_cold_start_reports_no_tombstones(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """Worthless to a client with no local state, and a privacy leak besides.

        Without this, anyone could enumerate the club's whole deletion history by
        starting a fresh sync.
        """
        gone = await _add_member(db_session, test_tenant.id, member_number="001")
        alive = await _add_member(db_session, test_tenant.id, member_number="002")
        assert await MemberRepository(db_session, test_tenant.id).soft_delete(gone.id)
        await _age_everything(db_session, test_tenant.id)

        changed, deleted, _cursor = await _drain(auth_client)

        assert deleted == []
        assert [row["id"] for row in changed] == [str(alive.id)]

    async def test_a_member_deleted_during_the_bootstrap_window_is_reported(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
        monkeypatch: Any,
    ) -> None:
        """A row delivered live early in a bootstrap can be deleted before the
        drain finishes. Its tombstone sorts after the cursor, so the still-running
        bootstrap is the only chance to hear about it — withhold it there and the
        device shows a deleted member as live until the cursor ages out.

        The lag is zeroed so the deletion becomes visible within the test instead
        of five seconds from now; the property under test is the bootstrap-window
        filter, not the watermark.
        """
        from app.sync import cursor as cursor_module

        monkeypatch.setattr(cursor_module, "CURSOR_SAFETY_LAG", timedelta(0))

        members = {
            str(m.id): m
            for m in [
                await _add_member(db_session, test_tenant.id, member_number=f"{i:03d}")
                for i in range(3)
            ]
        }
        await _age_everything(db_session, test_tenant.id)

        first_page = await auth_client.get(SYNC_MEMBERS, params={"limit": 1})
        changed, _deleted, meta = _sync(first_page.json())
        assert meta["has_more"] is True
        delivered = members[changed[0]["id"]]

        # Deleted mid-drain, at a position after the bootstrap began — the
        # cursor itself says when that was.
        assert await MemberRepository(db_session, test_tenant.id).soft_delete(delivered.id)
        token = meta["cursor"]
        payload = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
        started = datetime.fromisoformat(payload["bs"])
        await _set_updated_at(db_session, delivered, started + timedelta(milliseconds=1))

        _changed2, deleted2, _cursor = await _drain(auth_client, cursor=token)
        assert str(delivered.id) in {row["id"] for row in deleted2}, (
            "a deletion inside the bootstrap window was withheld — the client "
            "keeps showing this member until the cursor ages out"
        )

    async def test_a_page_of_only_tombstones_still_advances(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """The cursor comes from the merged scan, not from the delivered rows.

        Taken from `changed` alone, a page whose rows were all deletions would
        hand back the cursor it was given and the client would request the same
        page forever.
        """
        members = [
            await _add_member(db_session, test_tenant.id, member_number=f"{i:03d}")
            for i in range(3)
        ]
        base = await _age_everything(db_session, test_tenant.id)
        _changed, _deleted, cursor = await _drain(auth_client)

        repo = MemberRepository(db_session, test_tenant.id)
        assert await repo.soft_delete_many([m.id for m in members]) == 3
        await _age_everything(db_session, test_tenant.id, when=base + timedelta(seconds=1))

        first_page = await auth_client.get(SYNC_MEMBERS, params={"cursor": cursor, "limit": 1})
        changed, deleted, meta = _sync(first_page.json())
        assert changed == []
        assert len(deleted) == 1
        assert meta["cursor"] != cursor, "an all-tombstone page did not move the cursor"


class TestTenantIsolation:
    async def test_a_cursor_never_crosses_tenants(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        mine = await _add_member(db_session, test_tenant.id, member_number="001")
        other = Tenant(id=uuid.uuid4(), name="Other", slug="other-sync")
        db_session.add(other)
        await db_session.flush()
        theirs = await _add_member(db_session, other.id, member_number="999")

        await _age_everything(db_session, test_tenant.id)
        await _age_everything(db_session, other.id)

        changed, _deleted, _cursor = await _drain(auth_client)
        ids = {row["id"] for row in changed}
        assert str(mine.id) in ids
        assert str(theirs.id) not in ids


class TestCursorHandling:
    async def test_a_stale_cursor_is_refused_with_a_recoverable_code(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """409 and a name, so the client knows to bootstrap rather than retry."""
        ancient = start_cursor(bootstrap=False)
        old = encode_cursor(
            type(ancient)(
                updated_at=datetime.now(UTC) - CURSOR_MAX_AGE - timedelta(days=1),
                entity_id=uuid.uuid4(),
            )
        )
        response = await auth_client.get(SYNC_MEMBERS, params={"cursor": old})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CURSOR_TOO_OLD"

    async def test_a_malformed_cursor_is_a_400_not_a_500(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """A cursor arrives from a device that may have mangled it in storage."""
        for bad in ("not-base64!!", "", base64.urlsafe_b64encode(b"{}").decode()):
            response = await auth_client.get(SYNC_MEMBERS, params={"cursor": bad})
            assert response.status_code == 400, f"{bad!r} gave {response.status_code}"
            assert response.json()["error"]["code"] == "INVALID_CURSOR"

    async def test_a_naive_timestamp_is_refused(self, auth_client: AsyncClient) -> None:
        """Guessing a zone is how a client in UTC+2 silently skips two hours."""
        token = base64.urlsafe_b64encode(
            json.dumps(
                {"v": 1, "ts": "2026-01-01T00:00:00", "id": str(uuid.uuid4()), "phase": "live"}
            ).encode()
        ).decode()
        response = await auth_client.get(SYNC_MEMBERS, params={"cursor": token})
        assert response.status_code == 400

    async def test_an_empty_collection_still_returns_a_usable_cursor(
        self,
        auth_client: AsyncClient,
    ) -> None:
        response = await auth_client.get(SYNC_MEMBERS)
        changed, deleted, meta = _sync(response.json())
        assert changed == []
        assert deleted == []
        assert meta["has_more"] is False
        # Storable unconditionally, so the client needs no special case.
        assert meta["cursor"]

    async def test_a_bootstrap_that_read_nothing_still_finishes(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """Otherwise a club that starts empty never learns about a deletion.

        The bootstrap flag is what suppresses tombstones. If an empty first page
        left it set, the next sync would suppress them too — and the one after
        that, forever.
        """
        first = await auth_client.get(SYNC_MEMBERS)
        _c, _d, meta = _sync(first.json())

        member = await _add_member(db_session, test_tenant.id, member_number="001")
        base = await _age_everything(db_session, test_tenant.id)
        _c2, _d2, meta2 = _sync(
            (await auth_client.get(SYNC_MEMBERS, params={"cursor": meta["cursor"]})).json()
        )

        assert await MemberRepository(db_session, test_tenant.id).soft_delete(member.id)
        await _set_updated_at(db_session, member, base + timedelta(seconds=1))

        response = await auth_client.get(SYNC_MEMBERS, params={"cursor": meta2["cursor"]})
        _c3, deleted, _m3 = _sync(response.json())
        assert [row["id"] for row in deleted] == [str(member.id)]


class TestWatermark:
    async def test_a_just_written_row_waits_for_the_watermark(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        """Deliberately behind, and that is the point.

        `updated_at` is transaction-*start* time, so a long transaction can commit
        a row whose timestamp already sits behind a cursor issued meanwhile. The
        lag buys that transaction time to land in front of it. The push channel,
        not the poll, is what makes this invisible to a user.
        """
        await _add_member(db_session, test_tenant.id, member_number="001")

        response = await auth_client.get(SYNC_MEMBERS)
        changed, _deleted, _meta = _sync(response.json())
        assert changed == [], "a row newer than the watermark was served too early"

    async def test_it_becomes_visible_once_it_is_older_than_the_lag(
        self,
        auth_client: AsyncClient,
        db_session: AsyncSession,
        test_tenant: Tenant,
    ) -> None:
        member = await _add_member(db_session, test_tenant.id, member_number="001")
        await _set_updated_at(
            db_session, member, datetime.now(UTC) - CURSOR_SAFETY_LAG - timedelta(seconds=1)
        )

        changed, _deleted, _cursor = await _drain(auth_client)
        assert [row["id"] for row in changed] == [str(member.id)]


class TestManifest:
    async def test_the_manifest_lists_what_this_role_may_sync(
        self,
        auth_client: AsyncClient,
    ) -> None:
        response = await auth_client.get("/api/v1/sync/manifest")
        assert response.status_code == 200
        collections = response.json()["data"]["collections"]
        assert "members" in collections
        assert "events" in collections

    async def test_an_anonymous_caller_gets_nothing(self, anon_client: AsyncClient) -> None:
        """403, following the convention the rest of the API already uses."""
        assert (await anon_client.get("/api/v1/sync/manifest")).status_code == 403
        assert (await anon_client.get(SYNC_MEMBERS)).status_code == 403

    async def test_a_plain_member_may_sync_rounds_but_not_members(
        self,
        db_session: AsyncSession,
        fake_redis,  # type: ignore[no-untyped-def]
        test_user: Any,
        test_tenant: Tenant,
    ) -> None:
        """Rounds carry no personal data; the member mirror carries IBANs.

        A member needs the rounds to file a series under the right one — see
        the note on the collection in app/sync/registry.py.
        """
        import json as json_module

        from httpx import ASGITransport

        import app.redis as redis_module
        from app.database import get_db_session
        from app.main import app

        async def override_db():  # type: ignore[no-untyped-def]
            yield db_session

        app.dependency_overrides[get_db_session] = override_db
        redis_module._redis_client = fake_redis

        token = uuid.uuid4().hex
        await fake_redis.set(
            f"session:{token}",
            json_module.dumps(
                {
                    "user_id": str(test_user.id),
                    "tenant_id": str(test_tenant.id),
                    "role": "member",
                }
            ),
            ex=604800,
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={"unefy_session": token},
        ) as member_client:
            manifest = await member_client.get("/api/v1/sync/manifest")
            assert manifest.status_code == 200
            collections = manifest.json()["data"]["collections"]
            assert "competition-sessions" in collections
            assert "competitions" in collections
            assert "members" not in collections

            assert (await member_client.get("/api/v1/sync/competition-sessions")).status_code == 200
            assert (await member_client.get(SYNC_MEMBERS)).status_code == 403
