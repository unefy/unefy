import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.division import Division
from app.models.function import Function, MemberFunction
from app.repositories.function import FunctionRepository, MemberFunctionRepository
from app.repositories.member import MemberRepository
from app.schemas.function import (
    FunctionCreate,
    FunctionHolderResponse,
    FunctionUpdate,
    MemberFunctionCreate,
    MemberFunctionResponse,
    MemberFunctionUpdate,
)


class FunctionService:
    """Business logic for club offices and their terms.

    The invariants that live here rather than in the DB:
    - a member never holds the same function (same division) twice in
      overlapping periods — several *different* members at once are fine;
    - a `division`-level function is always assigned to a division, a
      `club`-level one never is;
    - a function with terms (even historic ones) is deactivated, not deleted.
    """

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.functions = FunctionRepository(session, tenant_id)
        self.assignments = MemberFunctionRepository(session, tenant_id)
        self.members = MemberRepository(session, tenant_id)

    # --- Functions ---

    async def create_function(self, data: FunctionCreate, created_by: uuid.UUID) -> Function:
        if await self.functions.get_by_name(data.name) is not None:
            raise ConflictError("A function with this name already exists")
        function = Function(
            **data.model_dump(),
            tenant_id=self.tenant_id,
            created_by=created_by,
            updated_by=created_by,
        )
        self.session.add(function)
        await self.session.flush()
        await self.session.refresh(function)
        return function

    async def update_function(
        self, function_id: uuid.UUID, data: FunctionUpdate, updated_by: uuid.UUID
    ) -> Function | None:
        function = await self.functions.get_by_id(function_id)
        if function is None:
            return None
        fields = data.model_dump(exclude_unset=True)
        new_name = fields.get("name")
        if (
            new_name
            and new_name != function.name
            and await self.functions.get_by_name(new_name) is not None
        ):
            raise ConflictError("A function with this name already exists")
        if (
            fields.get("level") is not None
            and fields["level"] != function.level
            and await self.assignments.count_for_function(function_id) > 0
        ):
            raise ConflictError("Cannot change the level of a function that has assignments")
        for field, value in fields.items():
            setattr(function, field, value)
        function.updated_by = updated_by
        await self.session.flush()
        await self.session.refresh(function)
        return function

    async def delete_function(self, function_id: uuid.UUID) -> None:
        function = await self.functions.get_by_id(function_id)
        if function is None:
            raise NotFoundError("Function not found")
        if await self.assignments.count_for_function(function_id) > 0:
            raise ConflictError(
                "This function has assignments (including historic ones);"
                " deactivate it instead of deleting"
            )
        await self.session.delete(function)
        await self.session.flush()

    # --- Assignments (terms of office) ---

    async def list_member_functions(self, member_id: uuid.UUID) -> list[MemberFunctionResponse]:
        if await self.members.get_by_id(member_id) is None:
            raise NotFoundError("Member not found")
        rows = await self.assignments.list_for_member(member_id)
        return [self._assignment_response(a, f, d) for a, f, d in rows]

    async def assign(
        self, member_id: uuid.UUID, data: MemberFunctionCreate, created_by: uuid.UUID
    ) -> MemberFunctionResponse:
        if await self.members.get_by_id(member_id) is None:
            raise NotFoundError("Member not found")
        function = await self.functions.get_by_id(data.function_id)
        if function is None:
            raise NotFoundError("Function not found")
        if not function.is_active:
            raise ValidationError("Cannot assign an inactive function")

        division = await self._check_division(function, data.division_id)
        await self._check_overlap(
            member_id=member_id,
            function_id=function.id,
            division_id=data.division_id,
            valid_from=data.valid_from,
            valid_to=data.valid_to,
        )

        assignment = MemberFunction(
            **data.model_dump(),
            member_id=member_id,
            tenant_id=self.tenant_id,
            created_by=created_by,
            updated_by=created_by,
        )
        self.session.add(assignment)
        await self.session.flush()
        await self.session.refresh(assignment)
        return self._assignment_response(assignment, function, division)

    async def update_assignment(
        self,
        member_id: uuid.UUID,
        assignment_id: uuid.UUID,
        data: MemberFunctionUpdate,
        updated_by: uuid.UUID,
    ) -> MemberFunctionResponse:
        assignment = await self._get_assignment(member_id, assignment_id)
        function = await self.functions.get_by_id(assignment.function_id)
        if function is None:  # pragma: no cover - FK RESTRICT makes this unreachable
            raise NotFoundError("Function not found")

        fields = data.model_dump(exclude_unset=True)
        division_id = fields.get("division_id", assignment.division_id)
        valid_from = fields.get("valid_from", assignment.valid_from)
        valid_to = fields.get("valid_to", assignment.valid_to)

        if valid_to is not None and valid_to < valid_from:
            raise ValidationError("valid_to must not be before valid_from")

        division = await self._check_division(function, division_id)
        await self._check_overlap(
            member_id=member_id,
            function_id=assignment.function_id,
            division_id=division_id,
            valid_from=valid_from,
            valid_to=valid_to,
            exclude_id=assignment.id,
        )

        for field, value in fields.items():
            setattr(assignment, field, value)
        assignment.updated_by = updated_by
        await self.session.flush()
        await self.session.refresh(assignment)
        return self._assignment_response(assignment, function, division)

    async def delete_assignment(self, member_id: uuid.UUID, assignment_id: uuid.UUID) -> None:
        """Hard delete — history is the feature, so this exists only to correct
        typos; ending a term means setting `valid_to`."""
        assignment = await self._get_assignment(member_id, assignment_id)
        await self.session.delete(assignment)
        await self.session.flush()

    async def holders(self, at: date) -> list[FunctionHolderResponse]:
        rows = await self.assignments.holders(at)
        return [
            FunctionHolderResponse(
                assignment_id=a.id,
                function_id=f.id,
                function_name=f.name,
                level=f.level,
                sort_order=f.sort_order,
                division_id=d.id if d else None,
                division_name=d.name if d else None,
                member_id=m.id,
                member_first_name=m.first_name,
                member_last_name=m.last_name,
                valid_from=a.valid_from,
                valid_to=a.valid_to,
                note=a.note,
            )
            for a, f, d, m in rows
        ]

    # --- Helpers ---

    async def _get_assignment(
        self, member_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> MemberFunction:
        assignment = await self.assignments.get_by_id(assignment_id)
        if assignment is None or assignment.member_id != member_id:
            raise NotFoundError("Assignment not found")
        return assignment

    async def _check_division(
        self, function: Function, division_id: uuid.UUID | None
    ) -> Division | None:
        if function.level == "division":
            if division_id is None:
                raise ValidationError("A division-level function requires a division")
        elif division_id is not None:
            raise ValidationError("A club-level function must not carry a division")
        if division_id is None:
            return None
        division = (
            await self.session.execute(
                select(Division)
                .where(Division.tenant_id == self.tenant_id)
                .where(Division.id == division_id)
            )
        ).scalar_one_or_none()
        if division is None:
            raise NotFoundError("Division not found")
        return division

    async def _check_overlap(
        self,
        *,
        member_id: uuid.UUID,
        function_id: uuid.UUID,
        division_id: uuid.UUID | None,
        valid_from: date,
        valid_to: date | None,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        if await self.assignments.overlap_exists(
            member_id=member_id,
            function_id=function_id,
            division_id=division_id,
            valid_from=valid_from,
            valid_to=valid_to,
            exclude_id=exclude_id,
        ):
            raise ConflictError("This member already holds this function in an overlapping period")

    def _assignment_response(
        self, assignment: MemberFunction, function: Function, division: Division | None
    ) -> MemberFunctionResponse:
        return MemberFunctionResponse(
            id=assignment.id,
            member_id=assignment.member_id,
            function_id=function.id,
            function_name=function.name,
            level=function.level,
            division_id=division.id if division else None,
            division_name=division.name if division else None,
            valid_from=assignment.valid_from,
            valid_to=assignment.valid_to,
            note=assignment.note,
            created_at=assignment.created_at,
            updated_at=assignment.updated_at,
        )
