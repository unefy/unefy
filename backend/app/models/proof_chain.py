"""Assurance level 1 — the append-only hash chain over proof events.

Level 0 (audit + freeze) answers "who changed what, when". The chain answers
the harder question: "has this history itself been rewritten?" Every proof
event — a session closing, a certificate being issued or revoked, a
correction after closing — appends one link; each link commits to the one
before it. Rewriting any past event breaks every hash after it.

The chain alone only holds against outsiders. In self-hosted mode the club
controls the server, so the head is periodically timestamped at an external
RFC-3161 authority (`ProofChainAnchor`) — the one measure that survives
"we could not have manipulated" being said by the party who could.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    LargeBinary,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantModel, TimestampMixin

CHAIN_ENTRY_TYPES = (
    "session_close",
    "certificate",
    "certificate_revoked",
    "record_amendment",
)


class ProofChainEntry(TenantModel, TimestampMixin):
    """Append-only. Never updated, never deleted — not even by retention.

    A link carries no personal data, only hashes and ids: what it proves is
    that a content with this fingerprint existed at this position, which is
    exactly what must survive after the content itself has been corrected or
    aged out.
    """

    __tablename__ = "proof_chain_entries"
    __table_args__ = (
        # The uniqueness is what serializes concurrent appends: two writers
        # that both read the same predecessor cannot both claim its successor
        # slot.
        Index("uq_proof_chain_tenant_seq", "tenant_id", "seq", unique=True),
    )

    # Per tenant, gapless in intent though not by constraint: 1, 2, 3, …
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)

    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # The session, certificate or record the link is about.
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # The previous link's chain_hash; 64 zeros for the genesis link.
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # SHA-256(prev_hash || content_hash) — the value the next link commits to.
    chain_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ProofChainAnchor(TenantModel, TimestampMixin):
    """A chain head, timestamped by an external RFC-3161 authority.

    The token is stored opaque: it is verified with standard tooling
    (`openssl ts -verify`) against the TSA's certificate, not by this code.
    Written only by the anchor task, and only when a TSA is configured — a
    row without a real token would be a claim with nothing behind it.
    """

    __tablename__ = "proof_chain_anchors"
    __table_args__ = (Index("ix_proof_chain_anchors_tenant_seq", "tenant_id", "seq_to"),)

    # The chain position the token covers: everything up to and including it.
    seq_to: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chain_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    tsa_token: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Which authority answered — the token is only checkable against its CA.
    tsa_url: Mapped[str] = mapped_column(String(255), nullable=False)

    anchored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
