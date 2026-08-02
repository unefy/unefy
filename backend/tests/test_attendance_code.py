"""Unit tests for the rotating attendance code.

Pure logic, no fixtures: every rule in `attendance_code` is a function of its
arguments, and the point of that design is that drift, expiry and forgery can
be tested by moving an integer rather than a clock.
"""

import uuid

import pytest

from app.services.attendance_code import (
    CODE_INTERVAL_SECONDS,
    SEED_GRACE_PERIODS,
    SEED_PERIOD_SECONDS,
    InvalidCodeError,
    build_code,
    counter_for,
    derive_seed,
    new_member_ref,
    parse_code,
    replay_key,
    seed_expires_at,
    seed_period,
    verify_code,
)

SECRET = "test-attendance-secret-at-least-32-chars"
TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
MEMBER = uuid.UUID("22222222-2222-2222-2222-222222222222")
OTHER_MEMBER = uuid.UUID("33333333-3333-3333-3333-333333333333")

# A fixed point in time, mid-period so tests are not accidentally sitting on a
# boundary. 2026-07-07 18:00 UTC.
NOW = 1_783_447_200


def _code(
    now: int = NOW, *, member_ref: str = "AAAAAAAAAAAAAAAA", member_id: uuid.UUID = MEMBER
) -> str:
    seed = derive_seed(SECRET, TENANT, member_id, seed_period(now))
    return build_code(seed, member_ref, TENANT, counter_for(now))


def _verify(code: str, *, now: int = NOW, member_id: uuid.UUID = MEMBER) -> None:
    verify_code(parse_code(code), secret=SECRET, tenant_id=TENANT, member_id=member_id, now=now)


def test_fresh_code_verifies() -> None:
    _verify(_code())


def test_member_ref_is_unique_and_well_formed() -> None:
    refs = {new_member_ref() for _ in range(100)}
    assert len(refs) == 100
    assert all(len(ref) == 16 and ref.isalnum() and ref.isupper() for ref in refs)


def test_code_does_not_contain_the_member_id() -> None:
    # The whole reason for the pseudonym: a photographed code must not identify
    # anyone to someone outside the club.
    assert str(MEMBER) not in _code()
    assert MEMBER.hex not in _code()


class TestDrift:
    """±1 counter of clock skew is accepted, more is not."""

    @pytest.mark.parametrize("steps", [-1, 0, 1])
    def test_within_tolerance(self, steps: int) -> None:
        _verify(_code(NOW + steps * CODE_INTERVAL_SECONDS), now=NOW)

    @pytest.mark.parametrize("steps", [-2, 2, 10])
    def test_outside_tolerance(self, steps: int) -> None:
        with pytest.raises(InvalidCodeError):
            _verify(_code(NOW + steps * CODE_INTERVAL_SECONDS), now=NOW)


class TestSeedAge:
    """An offline phone keeps working for a while, but not forever."""

    def test_seed_from_within_the_grace_window_still_verifies(self) -> None:
        # The phone last reached the server two days ago and is still showing
        # codes built from that seed. The code itself is current.
        stale_period = seed_period(NOW) - SEED_GRACE_PERIODS
        seed = derive_seed(SECRET, TENANT, MEMBER, stale_period)
        code = build_code(seed, "AAAAAAAAAAAAAAAA", TENANT, counter_for(NOW))

        _verify(code)

    def test_seed_older_than_the_grace_window_is_rejected(self) -> None:
        ancient = seed_period(NOW) - SEED_GRACE_PERIODS - 1
        seed = derive_seed(SECRET, TENANT, MEMBER, ancient)
        code = build_code(seed, "AAAAAAAAAAAAAAAA", TENANT, counter_for(NOW))

        with pytest.raises(InvalidCodeError):
            _verify(code)

    def test_seed_expiry_is_the_end_of_its_period(self) -> None:
        # Never in the past, never more than one period away — the app refreshes
        # against this value, so both bounds matter to it.
        expires_at = seed_expires_at(seed_period(NOW))
        assert NOW < expires_at <= NOW + SEED_PERIOD_SECONDS


class TestForgery:
    def test_another_members_code_does_not_verify(self) -> None:
        # Same window, same tenant, wrong person: the seed differs, so the MAC
        # cannot match.
        with pytest.raises(InvalidCodeError):
            _verify(_code(member_id=OTHER_MEMBER), member_id=MEMBER)

    def test_a_different_secret_does_not_verify(self) -> None:
        seed = derive_seed("a-completely-different-secret-value", TENANT, MEMBER, seed_period(NOW))
        code = build_code(seed, "AAAAAAAAAAAAAAAA", TENANT, counter_for(NOW))

        with pytest.raises(InvalidCodeError):
            _verify(code)

    def test_a_tampered_mac_does_not_verify(self) -> None:
        code = _code()
        head, mac = code.rsplit(".", 1)
        flipped = "B" if mac[0] != "B" else "C"

        with pytest.raises(InvalidCodeError):
            _verify(f"{head}.{flipped}{mac[1:]}")

    def test_swapping_the_member_ref_does_not_verify(self) -> None:
        # The ref is inside the MAC, so it cannot be relabelled to point at
        # someone else while keeping a valid signature.
        version, _ref, counter, mac = _code().split(".")

        with pytest.raises(InvalidCodeError):
            _verify(f"{version}.BBBBBBBBBBBBBBBB.{counter}.{mac}")

    def test_a_code_from_another_tenant_does_not_verify(self) -> None:
        other_tenant = uuid.UUID("44444444-4444-4444-4444-444444444444")
        seed = derive_seed(SECRET, other_tenant, MEMBER, seed_period(NOW))
        code = build_code(seed, "AAAAAAAAAAAAAAAA", other_tenant, counter_for(NOW))

        with pytest.raises(InvalidCodeError):
            _verify(code)


class TestParsing:
    @pytest.mark.parametrize(
        "code",
        [
            "",
            "nonsense",
            "uf1.SHORT.1.AAAAAAAAAAAAAAAA",
            "uf2.AAAAAAAAAAAAAAAA.1.AAAAAAAAAAAAAAAA",  # unknown version
            "uf1.AAAAAAAAAAAAAAAA.notanumber.AAAAAAAAAAAAAAAA",
            "uf1.AAAAAAAAAAAAAAAA.1",  # truncated
            "uf1.AAAAAAAAAAAA0189.1.AAAAAAAAAAAAAAAA",  # 0/1/8/9 are not Base32
        ],
    )
    def test_rejects_malformed(self, code: str) -> None:
        with pytest.raises(InvalidCodeError):
            parse_code(code)

    def test_accepts_lowercase_and_surrounding_space(self) -> None:
        # Scanners and hand-typed fallbacks both produce these.
        code = _code()
        assert parse_code(f"  {code.lower()}  ") == parse_code(code)


def test_replay_key_is_per_member_and_window() -> None:
    counter = counter_for(NOW)
    assert replay_key(TENANT, MEMBER, counter) != replay_key(TENANT, OTHER_MEMBER, counter)
    assert replay_key(TENANT, MEMBER, counter) != replay_key(TENANT, MEMBER, counter + 1)
    # Two seeds, same window: the key has to collide, or refetching a seed
    # mid-window would buy a second check-in.
    assert replay_key(TENANT, MEMBER, counter) == replay_key(TENANT, MEMBER, counter)
