"""The link at the bottom of a newsletter.

Unsubscribing has to be as easy as consenting, and it has to work from an
email — which means without a login, months later, from a device the club has
never seen. That rules out both a session and anything stored with a TTL: the
mail may sit in an inbox for a year, and a link that has quietly expired is a
member who cannot get out.

So the token is derived rather than stored: the member's id plus a keyed hash
of it. Nothing to write, nothing to clean up, and no table that grows with
every mailing.

Two consequences, both deliberate:

- **Rotating `SESSION_SECRET` invalidates every link that was ever sent.** A
  member who clicks an old one is told to unsubscribe from their own page
  instead. That is the price of not keeping a table of live tokens, and it is
  the cheap side of the trade.
- **The token names a member, not a mailing.** Unsubscribing is about the
  club's newsletter, not about the one message it arrived in.
"""

import hashlib
import hmac
import uuid

#: Mixed into the hash so a token from here can never be mistaken for — or
#: reused as — any other signed value built from the same secret.
_PURPOSE = "unsubscribe:v1"

#: Half of a SHA-256 in hex. 64 bits against forgery is plenty for a link
#: whose worst-case abuse is unsubscribing somebody from a club newsletter,
#: which they can undo on their own page.
_MAC_LENGTH = 16


def _mac(member_id: uuid.UUID, secret: str) -> str:
    message = f"{_PURPOSE}:{member_id}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()[:_MAC_LENGTH]


def sign(member_id: uuid.UUID, secret: str) -> str:
    """The token for the link. Stable: the same member always gets the same one."""
    return f"{member_id}.{_mac(member_id, secret)}"


def verify(token: str, secret: str) -> uuid.UUID | None:
    """The member the token names, or None if it does not hold up."""
    raw, _, mac = token.partition(".")
    if not mac:
        return None
    try:
        member_id = uuid.UUID(raw)
    except ValueError:
        return None
    # Constant-time: the comparison is the whole security of the link.
    if not hmac.compare_digest(mac, _mac(member_id, secret)):
        return None
    return member_id
