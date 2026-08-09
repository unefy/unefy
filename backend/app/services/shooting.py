"""The shooting-sport module: §14 evaluation and the issued proof.

The evaluation proposes, a board member issues — nothing here ever turns a
threshold into a certificate on its own (Art. 22 DSGVO, and plain club
hygiene). What *is* automatic is the freeze: issuing pins `record_ids` and a
`content_hash`, so the certificate stays attached to exactly the records that
were counted even after corrections or the retention job.
"""

import hashlib
import json
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.dependencies import AuthContext
from app.models.member import Member
from app.models.shooting import (
    ShootingProofCertificate,
    ShootingProofRule,
    ShootingRecordDetail,
)
from app.models.tenant import Tenant
from app.repositories.member import MemberRepository
from app.repositories.shooting import (
    ShootingCertificateRepository,
    ShootingDetailRepository,
    ShootingProofRepository,
    ShootingRuleRepository,
)
from app.schemas.shooting import (
    CertificateIssue,
    ShootingProofRuleCreate,
    ShootingProofRuleUpdate,
    ShootingRecordDetailUpdate,
)
from app.services.audit import diff, jsonable, record_tenant_action
from app.services.certificate_pdf import CertificateDay, CertificateDocument
from app.services.proof_chain import append_entry, canonical_hash

logger = structlog.get_logger()

# Readable enough to type from a printout, no ambiguous characters, and at
# ~57 bits far past guessable. Never the UUID: the code is the credential the
# public verify page accepts.
_CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
_CODE_LENGTH = 12


def _months_back(day: date, months: int) -> date:
    """The same day-of-month `months` earlier, clamped into the target month."""
    total = day.year * 12 + (day.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    for candidate_day in (day.day, 30, 29, 28):
        try:
            return date(year, month, candidate_day)
        except ValueError:
            continue
    raise AssertionError("unreachable: every month has a 28th")


def _evaluate(rule: ShootingProofRule, days: set[date]) -> tuple[int, int, bool]:
    """(session_count, months_covered, passed) for a set of shooting days.

    A "Termin" is a distinct calendar day, not a record: two range visits on
    one evening are one appointment in the sense of "18 in 12 months". The
    criteria are alternatives — see the model docstring.
    """
    months = {(d.year, d.month) for d in days}
    passed = False
    if rule.min_total_days is not None and len(days) >= rule.min_total_days:
        passed = True
    if rule.min_distinct_months is not None and len(months) >= rule.min_distinct_months:
        passed = True
    return len(days), len(months), passed


def _self_certified(rows: list[tuple[uuid.UUID, date, str, str]]) -> set[date]:
    """Days that rest on nothing but the member's own word.

    A day is *not* self-certified as soon as one record of it came from somebody
    else — the supervisor who ticks themselves off and is then scanned by a
    colleague has an attested evening, and the weaker record beside it changes
    nothing.
    """
    attested = {day for _, day, method, _ in rows if method != "self"}
    return {day for _, day, method, _ in rows if method == "self"} - attested


def _external_days(rows: list[tuple[uuid.UUID, date, str, str]]) -> set[date]:
    """Days claimed on a foreign range — always self-entries, by construction."""
    return {day for _, day, _, origin in rows if origin == "external"}


def _external_only_days(rows: list[tuple[uuid.UUID, date, str, str]]) -> set[date]:
    """Days whose only countable records are external claims.

    These can never be corroborated by desk-running: checking other people in
    proves presence at the *club*, while the claim under examination is about a
    different range entirely. A day that also carries a club record keeps the
    ordinary corroboration path.
    """
    club = {day for _, day, _, origin in rows if origin == "club"}
    return _external_days(rows) - club


class ShootingService:
    def __init__(self, session: AsyncSession, auth: AuthContext) -> None:
        self.session = session
        self.auth = auth
        self.tenant_id = auth.tenant
        self.rules = ShootingRuleRepository(session, self.tenant_id)
        self.details = ShootingDetailRepository(session, self.tenant_id)
        self.certificates = ShootingCertificateRepository(session, self.tenant_id)
        self.proof = ShootingProofRepository(session, self.tenant_id)
        self.members = MemberRepository(session, self.tenant_id)

    # --- Record details ---

    async def details_for_session(self, session_id: uuid.UUID) -> list[ShootingRecordDetail]:
        """What was shot at one evening, for the list that shows it."""
        return await self.details.list_for_session(session_id)

    async def own_details(self) -> list[ShootingRecordDetail]:
        """The caller's own shooting details, newest day first.

        Empty rather than an error when the account has no member record: an
        unlinked account (treasurer, external trainer) has no range days, which
        is a state and not a failure.
        """
        own = await self.members.get_by_user_id(self.auth.user_id)
        if own is None:
            return []
        return await self.details.list_for_member(own.id)

    async def upsert_detail(
        self, attendance_record_id: uuid.UUID, data: ShootingRecordDetailUpdate
    ) -> ShootingRecordDetail:
        """PATCH semantics over a row that may not exist yet.

        Upsert rather than POST-then-PATCH because the caller is a supervisor
        filling in a list — whether this attendance already has a detail row
        is bookkeeping the API should not make their problem.
        """
        # Through the attendance repo's scoping, so a record id from another
        # tenant is indistinguishable from a missing one.
        from app.repositories.attendance import AttendanceRecordRepository

        record = await AttendanceRecordRepository(self.session, self.tenant_id).get_by_id(
            attendance_record_id
        )
        if record is None:
            raise NotFoundError("Attendance record not found")

        # A plain member may fill in exactly one kind of row: their own
        # external self-entry. Club records are the supervisor's list — a
        # member writing their own round count into the club's evidence would
        # be the self-certification problem all over again, one field deeper.
        if self.auth.role not in ("owner", "admin", "board"):
            own = await self.members.get_by_user_id(self.auth.user_id)
            if own is None or record.member_id != own.id or record.origin != "external":
                raise ForbiddenError("Only the board edits club records")

        if record.member_id is None:
            # A guest's shots are the club's supervision problem, not anyone's
            # §14 proof — and the proof join would silently drop the detail
            # anyway. Refusing is honest, writing would be decorative.
            raise ConflictError("Guests carry no shooting detail", code="GUEST_RECORD")

        detail = await self.details.get_by_record(attendance_record_id)
        changes = data.model_dump(exclude_unset=True)
        if detail is None:
            detail = ShootingRecordDetail(
                tenant_id=self.tenant_id,
                attendance_record_id=attendance_record_id,
                created_by=self.auth.user_id,
                **changes,
            )
            self.session.add(detail)
            audit_changes = {
                field: {"from": None, "to": jsonable(v)} for field, v in changes.items()
            }
        else:
            before = {field: getattr(detail, field) for field in changes}
            for field, value in changes.items():
                setattr(detail, field, value)
            detail.updated_by = self.auth.user_id
            audit_changes = diff(before, changes)

        await self.session.flush()
        if audit_changes:
            await record_tenant_action(
                self.session,
                self.auth,
                "shooting_record_detail.updated",
                target_type="attendance_record",
                target_id=attendance_record_id,
                changes=audit_changes,
            )
        await self.session.commit()
        return detail

    # --- Rules ---

    async def create_rule(self, data: ShootingProofRuleCreate) -> ShootingProofRule:
        if await self.rules.get_by_key(data.rule_key) is not None:
            raise ConflictError("A rule with this key already exists")
        rule = await self.rules.create(data)
        rule.created_by = self.auth.user_id
        await self.session.commit()
        # The onupdate/server_default timestamps live server-side; without this
        # the response serializer would trigger a lazy load outside the
        # transaction.
        await self.session.refresh(rule)
        return rule

    async def update_rule(
        self, rule_id: uuid.UUID, data: ShootingProofRuleUpdate
    ) -> ShootingProofRule:
        rule = await self.rules.get_by_id(rule_id)
        if rule is None:
            raise NotFoundError("Rule not found")

        changes = data.model_dump(exclude_unset=True)
        merged = {
            field: changes.get(field, getattr(rule, field))
            for field in ("min_total_days", "min_distinct_months")
        }
        if all(value is None for value in merged.values()):
            # Caught here rather than left to the DB check, so the caller gets
            # a 422 that names the problem instead of a 500 from the constraint.
            raise ValidationError("A rule needs at least one criterion")

        for field, value in changes.items():
            setattr(rule, field, value)
        rule.updated_by = self.auth.user_id
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(rule)
        return rule

    async def delete_rule(self, rule_id: uuid.UUID) -> None:
        rule = await self.rules.get_by_id(rule_id)
        if rule is None:
            raise NotFoundError("Rule not found")
        # Hard delete: a rule is configuration, not evidence. Certificates
        # keep their own copy of what was tested (rule_key plus the counted
        # numbers), so the proof survives its rule.
        await self.session.delete(rule)
        await self.session.commit()

    # --- Evaluation ---

    async def _window(self, rule: ShootingProofRule, as_of: date | None) -> tuple[date, date]:
        if as_of is None:
            name = await self.session.scalar(
                select(Tenant.timezone).where(Tenant.id == self.tenant_id)
            )
            try:
                tz = ZoneInfo(name) if name else ZoneInfo("UTC")
            except (ZoneInfoNotFoundError, ValueError):
                tz = ZoneInfo("UTC")
            as_of = datetime.now(tz).date()
        # "The last 12 months" includes the reference day and starts the day
        # after the same date a year earlier — 2025-08-05..2026-08-04, not 366
        # days.
        start = _months_back(as_of, rule.window_months) + timedelta(days=1)
        return start, as_of

    async def evaluate(
        self, member_id: uuid.UUID, rule_key: str, as_of: date | None = None
    ) -> dict[str, object]:
        """The live §14 evaluation — a proposal, never a certificate."""
        member = await self.members.get_by_id(member_id)
        if member is None:
            raise NotFoundError("Member not found")
        rule = await self.rules.get_by_key(rule_key)
        if rule is None:
            raise NotFoundError("Rule not found")

        start, end = await self._window(rule, as_of)
        rows = await self.proof.countable_records(member_id, start, end)
        count, months, passed = _evaluate(rule, {occurred for _, occurred, _, _ in rows})
        self_days, corroborated = await self._self_entry_counts(member, rows, start, end)
        return {
            "member_id": member_id,
            "rule_key": rule_key,
            "period_start": start,
            "period_end": end,
            "session_count": count,
            "months_covered": months,
            "passed": passed,
            "self_certified_days": self_days,
            "corroborated_self_days": corroborated,
            "external_days": len(_external_days(rows)),
        }

    async def _self_entry_counts(
        self,
        member: Member,
        rows: list[tuple[uuid.UUID, date, str, str]],
        start: date,
        end: date,
    ) -> tuple[int, int]:
        """How many of the counted days the member vouched for themselves.

        Reported rather than deducted. Whether a self-certified day is worth
        anything is a question for the authority and the association, not for this
        code — what the code owes them is the ability to see it, which the raw day
        count cannot give them.

        The second number is what saves the honest case: of those days, the ones on
        which this person checked *other* people in. A supervisor who ran the desk
        all evening is attested by everybody else's records, which is better
        evidence than their own tick and does not depend on their word at all.
        """
        self_days = _self_certified(rows)
        if not self_days or member.user_id is None:
            return len(self_days), 0
        confirming = await self.proof.days_confirming_others(member.user_id, member.id, start, end)
        # Minus the purely external days: running the club's check-in desk
        # proves presence at the club, and cannot vouch for a visit the claim
        # places on some other range that same day.
        corroborated = (self_days & confirming) - _external_only_days(rows)
        return len(self_days), len(corroborated)

    # --- Certificates ---

    async def issue_certificate(self, data: CertificateIssue) -> ShootingProofCertificate:
        member = await self.members.get_by_id(data.member_id)
        if member is None:
            raise NotFoundError("Member not found")
        rule = await self.rules.get_by_key(data.rule_key)
        if rule is None:
            raise NotFoundError("Rule not found")

        start, end = await self._window(rule, data.as_of)
        rows = await self.proof.countable_records(data.member_id, start, end)
        count, months, passed = _evaluate(rule, {occurred for _, occurred, _, _ in rows})
        self_days, corroborated = await self._self_entry_counts(member, rows, start, end)
        record_ids = sorted(str(record_id) for record_id, _, _, _ in rows)

        certificate = ShootingProofCertificate(
            tenant_id=self.tenant_id,
            member_id=data.member_id,
            rule_key=data.rule_key,
            period_start=start,
            period_end=end,
            session_count=count,
            months_covered=months,
            self_certified_days=self_days,
            corroborated_self_days=corroborated,
            external_days=len(_external_days(rows)),
            result="passed" if passed else "failed",
            issued_at=datetime.now(UTC),
            issued_by_user_id=self.auth.user_id,
            record_ids=record_ids,
            content_hash="",
            verification_code=self._verification_code(),
            created_by=self.auth.user_id,
        )
        certificate.content_hash = _content_hash(certificate)
        self.session.add(certificate)
        await self.session.flush()

        # Assurance level 1: the certificate's own hash becomes a chain link,
        # so backdating one later would break every link after it.
        await append_entry(
            self.session,
            self.tenant_id,
            entry_type="certificate",
            subject_id=certificate.id,
            content_hash=certificate.content_hash,
        )

        await record_tenant_action(
            self.session,
            self.auth,
            "shooting_certificate.issued",
            target_type="shooting_certificate",
            target_id=certificate.id,
            changes={
                "member_id": {"from": None, "to": str(data.member_id)},
                "rule_key": {"from": None, "to": data.rule_key},
                "result": {"from": None, "to": certificate.result},
            },
        )
        await self.session.commit()
        return certificate

    def _verification_code(self) -> str:
        return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))

    async def revoke_certificate(
        self, certificate_id: uuid.UUID, *, reason: str
    ) -> ShootingProofCertificate:
        certificate = await self.certificates.get_by_id(certificate_id)
        if certificate is None:
            raise NotFoundError("Certificate not found")
        if certificate.revoked_at is not None:
            raise ConflictError("Certificate is already revoked")

        certificate.revoked_at = datetime.now(UTC)
        certificate.revoked_by_user_id = self.auth.user_id
        certificate.updated_by = self.auth.user_id
        certificate.revoke_reason = reason
        await self.session.flush()

        # A revocation changes what the chain's certificate link stands for,
        # so it gets its own link rather than silence.
        await append_entry(
            self.session,
            self.tenant_id,
            entry_type="certificate_revoked",
            subject_id=certificate.id,
            content_hash=canonical_hash(
                {
                    "certificate_id": str(certificate.id),
                    "content_hash": certificate.content_hash,
                    "revoked_at": certificate.revoked_at.isoformat(),
                    "reason": reason,
                    "actor_user_id": str(self.auth.user_id),
                }
            ),
        )

        await record_tenant_action(
            self.session,
            self.auth,
            "shooting_certificate.revoked",
            target_type="shooting_certificate",
            target_id=certificate.id,
            reason=reason,
        )
        await self.session.commit()
        return certificate

    async def certificate_document(
        self, certificate_id: uuid.UUID, *, web_app_url: str, with_days: bool = False
    ) -> CertificateDocument:
        """One certificate as the printable document.

        Resolved here rather than in the route: the member's number, the rule's
        label and the check URL all come from different places, and a route
        that assembled them would be doing the service's job.
        """
        certificate = await self.certificates.get_by_id(certificate_id)
        if certificate is None:
            raise NotFoundError("Certificate not found")

        row = (
            await self.session.execute(
                select(Member.first_name, Member.last_name, Member.member_number)
                .where(Member.tenant_id == self.tenant_id)
                .where(Member.id == certificate.member_id)
            )
        ).first()
        club = (
            await self.session.execute(select(Tenant.name).where(Tenant.id == self.tenant_id))
        ).scalar_one()
        rule = await self.rules.get_by_key(certificate.rule_key)

        # The annex reads the ids the certificate froze, not today's evaluation:
        # it has to show the days this document rests on. Fewer rows than ids
        # means the retention job has been through — said out loud on the page
        # rather than printed as a shorter list.
        days: tuple[CertificateDay, ...] = ()
        missing = 0
        if with_days:
            rows = await self.proof.records_for_certificate(certificate.record_ids)
            days = tuple(
                CertificateDay(
                    day=day,
                    discipline=discipline,
                    weapon_category=weapon,
                    rounds_fired=rounds,
                    origin=origin,
                )
                for day, origin, discipline, weapon, rounds in rows
            )
            missing = max(0, len(certificate.record_ids) - len(rows))

        return CertificateDocument(
            club_name=club,
            member_name=f"{row[0]} {row[1]}" if row else "—",
            member_number=row[2] if row else None,
            # The key is a stable identifier, not a sentence — but a rule that
            # was deleted since must not leave the page blank.
            rule_label=rule.label if rule else certificate.rule_key,
            period_start=certificate.period_start,
            period_end=certificate.period_end,
            session_count=certificate.session_count,
            months_covered=certificate.months_covered,
            self_certified_days=certificate.self_certified_days,
            external_days=certificate.external_days,
            passed=certificate.result == "passed",
            issued_on=certificate.issued_at.date(),
            verification_code=certificate.verification_code,
            verification_url=(f"{web_app_url.rstrip('/')}/verify/{certificate.verification_code}"),
            revoked=certificate.revoked_at is not None,
            days=days,
            missing_days=missing,
        )

    async def member_name(self, member_id: uuid.UUID) -> str | None:
        result = await self.session.execute(
            select(Member.first_name, Member.last_name)
            .where(Member.tenant_id == self.tenant_id)
            .where(Member.id == member_id)
        )
        row = result.first()
        return f"{row[0]} {row[1]}" if row else None


def _content_hash(certificate: ShootingProofCertificate) -> str:
    """SHA-256 over the canonical JSON of what was certified.

    Canonical means: fixed field set, sorted keys, sorted record ids, ISO
    dates. Anyone holding the certificate row can recompute this and compare —
    that is the whole claim the hash makes.
    """
    canonical = json.dumps(
        {
            "tenant_id": str(certificate.tenant_id),
            "member_id": str(certificate.member_id),
            "rule_key": certificate.rule_key,
            "period_start": certificate.period_start.isoformat(),
            "period_end": certificate.period_end.isoformat(),
            "session_count": certificate.session_count,
            "months_covered": certificate.months_covered,
            "self_certified_days": certificate.self_certified_days,
            "corroborated_self_days": certificate.corroborated_self_days,
            "external_days": certificate.external_days,
            "result": certificate.result,
            "record_ids": sorted(certificate.record_ids),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
