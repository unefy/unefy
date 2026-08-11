import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.base import BaseSchema


class TemplateCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    #: Bounded generously rather than tightly: this is a letter, and a club
    #: that needs two pages of wording is not doing anything wrong.
    body: str = Field(min_length=1, max_length=20000)
    include_letterhead: bool = True
    include_footer: bool = True
    verifiable: bool = True
    is_active: bool = True


class TemplateUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = Field(default=None, min_length=1, max_length=20000)
    include_letterhead: bool | None = None
    include_footer: bool | None = None
    verifiable: bool | None = None
    is_active: bool | None = None


class TemplateResponse(BaseSchema):
    id: uuid.UUID
    name: str
    title: str
    body: str
    include_letterhead: bool
    include_footer: bool
    verifiable: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class VariableResponse(BaseSchema):
    """One placeholder the editor may offer. The German label lives in the web
    app's messages, keyed by `key` — UI text belongs there."""

    key: str
    description: str


class StarterResponse(BaseSchema):
    """A ready-made wording the club can start from.

    Carries the caveat with it: a draft handed over without saying what to
    check is worse than no draft, because it looks finished.
    """

    key: str
    name: str
    title: str
    body: str
    caveat: str
    include_letterhead: bool
    include_footer: bool
    verifiable: bool


class TemplatePreview(BaseSchema):
    """Rendering a draft before it is saved, against stand-in values."""

    body: str = Field(min_length=0, max_length=20000)


class PreviewResponse(BaseSchema):
    rendered: str
    #: Names in the text that are not in the set. Reported rather than raised
    #: so the editor can mark all of them at once.
    unknown: list[str]


class IssueRequest(BaseSchema):
    template_id: uuid.UUID


class RevokeRequest(BaseSchema):
    reason: str = Field(min_length=1, max_length=1000)


class IssuedDocumentResponse(BaseSchema):
    id: uuid.UUID
    member_id: uuid.UUID
    template_id: uuid.UUID | None = None
    template_name: str
    title: str
    body: str
    issued_at: datetime
    revoked_at: datetime | None = None
    revoke_reason: str | None = None
    verification_code: str | None = None
