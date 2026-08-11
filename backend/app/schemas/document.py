import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema

#: Mirrors `SIGNATURE_MODES`; spelled out because a Literal cannot be built
#: from a tuple. A test holds the two against each other.
SignatureMode = Literal["none", "machine", "line"]


class TemplateCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    #: Bounded generously rather than tightly: this is a letter, and a club
    #: that needs two pages of wording is not doing anything wrong.
    body: str = Field(min_length=1, max_length=20000)
    include_letterhead: bool = True
    include_footer: bool = True
    verifiable: bool = True
    #: How the document ends. `line` is the default because it is what every
    #: document did before the setting existed.
    signature_mode: SignatureMode = "line"
    is_active: bool = True


class TemplateUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = Field(default=None, min_length=1, max_length=20000)
    include_letterhead: bool | None = None
    include_footer: bool | None = None
    verifiable: bool | None = None
    signature_mode: SignatureMode | None = None
    is_active: bool | None = None


class TemplateResponse(BaseSchema):
    id: uuid.UUID
    name: str
    title: str
    body: str
    include_letterhead: bool
    include_footer: bool
    verifiable: bool
    signature_mode: SignatureMode
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
    signature_mode: SignatureMode


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


class SignatureSubmit(BaseSchema):
    """The drawing from the canvas, as a data URL or bare base64."""

    signature_png: str = Field(min_length=1, max_length=400_000)


class SignatureLinkResponse(BaseSchema):
    """Where to sign, and the same thing as a QR to point a phone at.

    The QR travels as its module matrix rather than as an image: the backend
    already has the encoder, and a matrix is drawn by the browser without a
    dependency and without putting server-made markup into the page.
    """

    url: str
    expires_in: int
    #: One string per row, "0" and "1" per module.
    qr: list[str]


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
    signature_mode: SignatureMode
    #: When it was signed on a device — never the drawing itself.
    signed_at: datetime | None = None
