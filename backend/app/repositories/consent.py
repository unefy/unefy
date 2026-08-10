import uuid

from sqlalchemy import Select, select

from app.models.consent import MemberConsent


def members_who_refused(tenant_id: uuid.UUID, kind: str) -> Select[tuple[uuid.UUID]]:
    """Ids of members whose *newest* answer for this kind is no.

    A subquery rather than a loaded set, so a caller can exclude these members
    inside its own query instead of paginating around a Python list.

    `DISTINCT ON` rather than a max-timestamp comparison: two rows can share a
    timestamp — the join form writes all three answers at the same instant —
    and the id tie-break makes "newest" unambiguous. Postgres-only, which this
    project is.

    Members who were never asked are absent here, and that is the point: the
    absence of an answer is not a refusal.
    """
    newest = (
        select(MemberConsent.member_id, MemberConsent.granted)
        .where(MemberConsent.tenant_id == tenant_id)
        .where(MemberConsent.kind == kind)
        .order_by(
            MemberConsent.member_id,
            MemberConsent.recorded_at.desc(),
            MemberConsent.id.desc(),
        )
        .distinct(MemberConsent.member_id)
        .subquery()
    )
    return select(newest.c.member_id).where(newest.c.granted.is_(False))
