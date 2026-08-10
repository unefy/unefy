"""Joining a club: the application, and the decision on it.

Admission is a decision a board takes. A public form cannot take it, so the
form produces an application and nothing else — the member record comes into
existence only when somebody accepts.

That split is not bureaucracy. A pending application must not appear in a
member list, must not receive a due, and must not count towards anybody's §14
proof; and an applicant who is turned down has data the club has to keep
separately from its members' and delete on a schedule of its own.
"""

import uuid
from datetime import UTC, date, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.application import MembershipApplication
from app.models.division import Division
from app.models.due import FeeType, MemberFee
from app.models.member import Member
from app.models.tenant import Tenant
from app.repositories.member import MemberRepository
from app.schemas.application import ApplicationSubmit
from app.schemas.member import MemberCreate
from app.services.member import MemberService

logger = structlog.get_logger()


class ApplicationService:
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # --- The public side ---

    async def submit(self, data: ApplicationSubmit) -> MembershipApplication:
        """Record an application. Never decides anything.

        A fee type or division the club does not offer is refused — not to be
        strict, but because a stored wish nobody can fulfil would be read as a
        promise at the decision.

        Deliberately silent about whether this person is already a member: the
        form answers the same way either way. Otherwise it becomes a way to ask
        the club who belongs to it.
        """
        if data.fee_type_id is not None:
            await self._require_offered_fee(data.fee_type_id)
        if data.division_id is not None:
            await self._require_division(data.division_id)

        application = MembershipApplication(
            tenant_id=self.tenant_id,
            status="pending",
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            email=str(data.email) if data.email else None,
            phone=data.phone,
            mobile=data.mobile,
            birthday=data.birthday,
            gender=data.gender,
            street=data.street,
            zip_code=data.zip_code,
            city=data.city,
            country=data.country,
            message=data.message,
            fee_type_id=data.fee_type_id,
            division_id=data.division_id,
            iban=data.iban,
            bic=data.bic,
            account_holder=data.account_holder,
            # The date the mandate was granted is today; the reference follows
            # on acceptance, when there is a membership to reference.
            sepa_mandate_date=date.today() if data.grant_sepa_mandate else None,
            privacy_accepted_at=datetime.now(UTC),
            consent_photos=data.consent_photos,
            consent_newsletter=data.consent_newsletter,
            consent_directory=data.consent_directory,
        )
        self.session.add(application)
        await self.session.flush()
        logger.info("application_submitted", tenant_id=str(self.tenant_id))
        return application

    # --- The board's side ---

    async def get(self, application_id: uuid.UUID) -> MembershipApplication:
        application = (
            await self.session.execute(
                select(MembershipApplication)
                .where(MembershipApplication.tenant_id == self.tenant_id)
                .where(MembershipApplication.id == application_id)
            )
        ).scalar_one_or_none()
        if application is None:
            raise NotFoundError("Application not found")
        return application

    async def list(self, *, status: str | None = None) -> list[MembershipApplication]:
        query = (
            select(MembershipApplication)
            .where(MembershipApplication.tenant_id == self.tenant_id)
            .order_by(MembershipApplication.created_at.desc())
        )
        if status:
            query = query.where(MembershipApplication.status == status)
        return list((await self.session.execute(query)).scalars().all())

    async def accept(self, application_id: uuid.UUID, *, decided_by: uuid.UUID) -> Member:
        """Admit the applicant — the only path that creates a member here.

        The member number comes from `MemberService`, which locks the tenant
        row to allocate it. Doing that by hand would be a second place where
        two clubs' worth of numbering logic could drift apart.
        """
        application = await self.get(application_id)
        self._require_pending(application)

        members = MemberService(MemberRepository(self.session, self.tenant_id), self.session)
        member = await members.create(
            MemberCreate(
                first_name=application.first_name,
                last_name=application.last_name,
                email=application.email,
                phone=application.phone,
                mobile=application.mobile,
                birthday=application.birthday,
                gender=application.gender,
                street=application.street,
                zip_code=application.zip_code,
                city=application.city,
                country=application.country,
                # Membership starts when it was granted, not when the form was
                # filled in — the applicant does not decide their joining date.
                joined_at=date.today(),
                status="active",
                iban=application.iban,
                bic=application.bic,
                account_holder=application.account_holder,
            ),
            created_by=decided_by,
        )

        # The mandate reference names the membership, which is why it can only
        # be built now: before this moment there was no member number.
        if application.sepa_mandate_date is not None:
            member.sepa_mandate_reference = f"M-{member.member_number}"
            member.sepa_mandate_date = application.sepa_mandate_date

        # The requested division is not carried over, because there is nowhere
        # to carry it to: members are not linked to divisions today (only
        # attendance and offices are). It stays on the application as what the
        # applicant asked for, and the board reads it there.

        if application.fee_type_id is not None:
            self.session.add(
                MemberFee(
                    tenant_id=self.tenant_id,
                    member_id=member.id,
                    fee_type_id=application.fee_type_id,
                    valid_from=member.joined_at,
                    created_by=decided_by,
                    updated_by=decided_by,
                )
            )

        application.status = "accepted"
        application.decided_at = datetime.now(UTC)
        application.decided_by_user_id = decided_by
        application.member_id = member.id
        await self.session.flush()
        # The mandate assignment above dirties the member, and the flush that
        # follows expires its `updated_at`. Without this the caller serialising
        # the member would have to load it from inside Pydantic, where there is
        # no greenlet to await on.
        await self.session.refresh(member)

        logger.info(
            "application_accepted",
            tenant_id=str(self.tenant_id),
            member_id=str(member.id),
        )
        return member

    async def reject(
        self, application_id: uuid.UUID, *, decided_by: uuid.UUID, note: str | None
    ) -> MembershipApplication:
        """Turn an application down. The note stays in the club's record.

        Nothing is sent anywhere: telling the applicant is a human act, and a
        rejection that arrives as an automated mail is worse than a call.
        """
        application = await self.get(application_id)
        self._require_pending(application)

        application.status = "rejected"
        application.decided_at = datetime.now(UTC)
        application.decided_by_user_id = decided_by
        application.decision_note = note
        await self.session.flush()
        return application

    # --- Helpers ---

    def _require_pending(self, application: MembershipApplication) -> None:
        if application.status != "pending":
            raise ConflictError(
                "This application has already been decided",
                code="APPLICATION_DECIDED",
            )

    async def _require_offered_fee(self, fee_type_id: uuid.UUID) -> None:
        found = (
            await self.session.execute(
                select(FeeType.id)
                .where(FeeType.tenant_id == self.tenant_id)
                .where(FeeType.id == fee_type_id)
                .where(FeeType.is_active.is_(True))
                .where(FeeType.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if found is None:
            raise ValidationError("The club does not offer this fee type")

    async def _require_division(self, division_id: uuid.UUID) -> None:
        found = (
            await self.session.execute(
                select(Division.id)
                .where(Division.tenant_id == self.tenant_id)
                .where(Division.id == division_id)
            )
        ).scalar_one_or_none()
        if found is None:
            raise ValidationError("The club has no such division")


async def tenant_by_slug(session: AsyncSession, slug: str) -> Tenant:
    """Resolve the club behind a public join URL.

    One 404 for all three cases — no such club, inactive, join form switched
    off. A club that has not opened its form should not be discoverable
    through it, and the page must not answer questions about which clubs exist
    on this server.
    """
    tenant = (
        await session.execute(
            select(Tenant)
            .where(Tenant.slug == slug)
            .where(Tenant.is_active.is_(True))
            .where(Tenant.applications_enabled.is_(True))
        )
    ).scalar_one_or_none()
    if tenant is None:
        raise NotFoundError("Unknown club")
    return tenant
