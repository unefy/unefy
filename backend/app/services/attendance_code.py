"""The rotating member code that a supervisor scans.

The shape is `uf1.<member_ref>.<counter>.<mac>`. A member's app fetches a seed
once, then computes a fresh code every 30 seconds without asking the server
again — shooting ranges are often in basements with no signal, so offline
capability is a requirement rather than a nicety.

Three properties matter and each costs one design decision:

* **A photographed code must not leak a member id.** Hence `member_ref`, a
  per-tenant pseudonym stored on the member, never the primary key.
* **A screenshot must not travel.** The counter ties the code to a 30-second
  window, and the caller burns it in Redis so it cannot be presented twice.
* **The server must not have to store seeds.** They are derived from
  `ATTENDANCE_SECRET`, so there is no table to keep, no cleanup job and no
  replication concern; rotating the secret invalidates every outstanding seed.

This module is pure: no database, no Redis, no clock beyond what the caller
passes in. Everything here is a function of its arguments, which is what makes
the drift and expiry rules testable without a fixture.
"""

import base64
import hashlib
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass

# Version prefix. A future format change gets `uf2` and both can be accepted
# during the transition instead of every member's app breaking at once.
CODE_VERSION = "uf1"

# One code per half minute. Short enough that a photo is stale by the time it
# is passed on, long enough to survive a slow camera and a shaky hand.
CODE_INTERVAL_SECONDS = 30

# Clock drift between the member's phone and the server, in counter steps.
# ±1 gives 30 to 60 seconds of slack in each direction.
COUNTER_TOLERANCE = 1

SEED_PERIOD_SECONDS = 86_400

# How many expired seed periods still verify. The member's phone may have been
# offline for a while and is still showing codes from the last seed it managed
# to fetch; two periods is the "Kulanz bei fehlender Verbindung" from the plan.
SEED_GRACE_PERIODS = 2

# 10 bytes of MAC, Base32 without padding — 16 characters. Truncating a
# SHA-256 HMAC is standard practice (RFC 4226 does the same for TOTP); 80 bits
# is far beyond guessable inside a 30-second window that also rate-limits.
MAC_BYTES = 10

MEMBER_REF_BYTES = 10

# Case-insensitive, because a scanner reads what it is given and the hand-typed
# fallback will not shout. The payload is upper-cased after matching, not
# before: upper-casing first would turn the `uf1` prefix into `UF1` and nothing
# would ever parse.
_CODE_PATTERN = re.compile(
    rf"^{CODE_VERSION}\.([A-Z2-7]{{16}})\.(\d{{1,12}})\.([A-Z2-7]{{16}})$",
    re.IGNORECASE,
)


class InvalidCodeError(Exception):
    """The code is malformed, expired, or does not verify.

    One exception for all three on purpose: telling a caller *why* a code
    failed tells an attacker which half of the guess was right.
    """


@dataclass(frozen=True)
class ParsedCode:
    member_ref: str
    counter: int
    mac: str


def _b32(raw: bytes) -> str:
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def new_member_ref() -> str:
    """A member's tenant-wide pseudonym.

    Random rather than derived from the id: a derived pseudonym is only as
    private as the secret it came from, and this value ends up printed on
    things. 80 bits of randomness, Base32, so it stays readable if it ever has
    to be typed by hand.
    """
    return _b32(secrets.token_bytes(MEMBER_REF_BYTES))


def seed_period(now: int) -> int:
    """The 24-hour bucket a unix timestamp falls into."""
    return now // SEED_PERIOD_SECONDS


def seed_expires_at(period: int) -> int:
    """When the seed for `period` stops being handed out.

    Note this is the end of the bucket, not 24 hours from issuance: a phone
    asking at 23:50 gets a seed good for ten minutes and refetches. The app
    treats this as an expiry to refresh against, and the verifier's grace
    periods mean a late refresh is not a lockout.
    """
    return (period + 1) * SEED_PERIOD_SECONDS


def derive_seed(
    secret: str,
    tenant_id: uuid.UUID,
    member_id: uuid.UUID,
    period: int,
    version: int = 0,
) -> str:
    """The member's seed for one 24-hour period.

    Derived, not stored: the server can recompute any seed it ever issued, so
    there is nothing to persist and nothing to leak at rest beyond the one
    secret that already has to be protected.

    [version] is the member's `seed_version`, and bumping it is what a
    revocation *is*: every seed the old version produced stops verifying at
    once, on every device that holds one. Until this existed the only way to
    take a lost phone's codes away was to wait out the grace window — three
    days in which whoever found it could check that member in.

    Version 0 is deliberately hashed exactly as before it existed. Folding it
    in unconditionally would have invalidated every seed already on every
    phone, and an app holding a seed it believes is current does not refetch:
    the club would have discovered the change at the door, which is the one
    place none of this may fail.
    """
    suffix = "" if version == 0 else f":{version}"
    message = f"seed:{tenant_id}:{member_id}:{period}{suffix}".encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).digest()
    return _b32(digest)


def counter_for(now: int) -> int:
    return now // CODE_INTERVAL_SECONDS


def build_code(seed: str, member_ref: str, tenant_id: uuid.UUID, counter: int) -> str:
    """What the member's device shows. Mirrored by the Android implementation."""
    return f"{CODE_VERSION}.{member_ref}.{counter}.{_mac(seed, member_ref, tenant_id, counter)}"


def _mac(seed: str, member_ref: str, tenant_id: uuid.UUID, counter: int) -> str:
    message = f"{tenant_id}|{member_ref}|{counter}".encode()
    digest = hmac.new(seed.encode(), message, hashlib.sha256).digest()
    return _b32(digest[:MAC_BYTES])


def parse_code(code: str) -> ParsedCode:
    """Structure only — says nothing about whether the code is genuine."""
    match = _CODE_PATTERN.match(code.strip())
    if match is None:
        raise InvalidCodeError("Malformed attendance code")
    return ParsedCode(
        member_ref=match.group(1).upper(),
        counter=int(match.group(2)),
        mac=match.group(3).upper(),
    )


def verify_code(
    parsed: ParsedCode,
    *,
    secret: str,
    tenant_id: uuid.UUID,
    member_id: uuid.UUID,
    now: int,
    version: int = 0,
) -> None:
    """Raise [InvalidCodeError] unless this code was produced by this member.

    The caller has already resolved `member_ref` to a member; this checks that
    the MAC matches and that the code is from the current window.

    [version] is checked at the *current* value only, never at the old one:
    that is what makes a bump a revocation rather than a rename. Codes from
    before it stop verifying immediately, grace window included.
    """
    current = counter_for(now)
    if abs(parsed.counter - current) > COUNTER_TOLERANCE:
        raise InvalidCodeError("Attendance code has expired")

    # The phone may still be holding an older seed, so try this period and the
    # grace ones. Derived from the code's own counter rather than from `now`,
    # because the two can straddle a period boundary.
    code_period = seed_period(parsed.counter * CODE_INTERVAL_SECONDS)
    for period in range(code_period, code_period - SEED_GRACE_PERIODS - 1, -1):
        if period < 0:
            break
        seed = derive_seed(secret, tenant_id, member_id, period, version)
        expected = _mac(seed, parsed.member_ref, tenant_id, parsed.counter)
        # compare_digest, not ==: string comparison returns early on the first
        # differing character and leaks how much of a guess was right.
        if hmac.compare_digest(expected, parsed.mac):
            return

    raise InvalidCodeError("Attendance code did not verify")


def replay_key(tenant_id: uuid.UUID, member_id: uuid.UUID, counter: int) -> str:
    """Redis key that makes a code single-use.

    Keyed by counter rather than by the whole code so that two devices holding
    different seeds for the same window still collide — otherwise a member who
    refetched a seed mid-window could check in twice.
    """
    return f"checkin:{tenant_id}:{member_id}:{counter}"


# One window plus the drift either side, rounded up. Shorter and a code could
# be replayed after its key expired but before it stopped verifying.
REPLAY_TTL_SECONDS = CODE_INTERVAL_SECONDS * (2 * COUNTER_TOLERANCE + 1)
