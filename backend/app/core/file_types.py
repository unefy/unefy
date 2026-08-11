"""What a file actually is, as opposed to what it is called.

An extension is a claim and `Content-Type` from a browser is a guess, so
neither decides what gets stored. The first few kilobytes decide, against a
positive list: PDF, PNG, JPEG, WebP, ODF, OOXML, plain text, CSV, iCalendar.
Anything else is refused rather than stored "just in case" — the library is a
place for a club's paperwork, not a general file host.

**SVG is deliberately absent.** An SVG is executable markup; served from the
application's own origin it is a script with the user's session, and the
document library would be the way to upload one.

**There is no virus scanner**, and this is where that gap is written down.
ClamAV would be another service in the compose file and another gigabyte of
signatures a club has to keep current. What stands in its place: nothing here
is ever executed, the positive list keeps out the formats that carry macros
with them (`.doc`, `.xls`, `.exe`, plain ZIP), delivery is `attachment` with
`nosniff` for everything but PDFs and images, and the detected type — not the
claimed one — is what gets served back.
"""

import codecs
from pathlib import PurePosixPath

#: How much of the file the detector needs. A local ZIP header plus the first
#: few entries fit comfortably; for text it is a generous sample.
HEAD_BYTES = 8192


class UnsupportedFileTypeError(Exception):
    """The bytes are not one of the accepted types."""


#: Detected type → the extensions a club is likely to have on disk for it.
#: Used for text, which has no signature to check, and to name a downloaded
#: file sensibly.
ALLOWED_TYPES: dict[str, tuple[str, ...]] = {
    "application/pdf": (".pdf",),
    "image/png": (".png",),
    "image/jpeg": (".jpg", ".jpeg"),
    "image/webp": (".webp",),
    "application/vnd.oasis.opendocument.text": (".odt",),
    "application/vnd.oasis.opendocument.spreadsheet": (".ods",),
    "application/vnd.oasis.opendocument.presentation": (".odp",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (".docx",),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (".xlsx",),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (".pptx",),
    "text/plain": (".txt",),
    "text/csv": (".csv",),
    "text/calendar": (".ics",),
}

#: Types whose first bytes name them outright.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)

#: ODF stores its own media type as the first entry of the ZIP, uncompressed,
#: which is the one office format that says what it is inside the file.
_ODF_TYPES = (
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
)

#: OOXML says only that it is OOXML. Which of the three it is shows up in the
#: entry paths, which sit early enough in the archive to be in the head.
_OOXML_MARKERS: tuple[tuple[bytes, str], ...] = (
    (b"word/", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    (b"xl/", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    (b"ppt/", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
)

_TEXT_BY_EXTENSION = {
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".ics": "text/calendar",
}


def extension_of(filename: str) -> str:
    """The lower-cased suffix, taking the name as a name and not as a path."""
    return PurePosixPath(filename.replace("\\", "/")).suffix.lower()


def detect_content_type(head: bytes, filename: str) -> str:
    """The type of a file from its first bytes. Raises for anything else.

    `filename` is consulted only where the bytes genuinely cannot decide: text
    files have no signature, so `.csv` and `.txt` are told apart by their name
    once the content has been confirmed to be text at all. Everywhere else the
    bytes win outright — a PDF called `photo.png` is stored, and served, as a
    PDF.
    """
    if not head:
        raise UnsupportedFileTypeError("The file is empty")

    for signature, content_type in _SIGNATURES:
        if head.startswith(signature):
            return content_type

    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"

    if head[:2] == b"PK":
        return _detect_zip_container(head, filename)

    return _detect_text(head, filename)


def _detect_zip_container(head: bytes, filename: str) -> str:
    """ODF and OOXML are ZIP files; a plain ZIP is not accepted.

    This is the check that catches the archive renamed to `.pdf`: it gets this
    far because it really is a ZIP, and stops here because it carries neither
    an ODF media type nor an OOXML content-types entry.
    """
    if head[:4] != b"PK\x03\x04":
        raise UnsupportedFileTypeError("Damaged or empty archive")

    # ODF: `mimetype` is the first entry, stored rather than deflated, so its
    # value sits at a fixed offset right after the local file header.
    if head[30:38] == b"mimetype":
        declared = head[38:150].decode("ascii", errors="replace")
        for odf_type in _ODF_TYPES:
            if declared.startswith(odf_type):
                return odf_type
        raise UnsupportedFileTypeError("Unsupported OpenDocument type")

    if b"[Content_Types].xml" in head[:512]:
        for marker, content_type in _OOXML_MARKERS:
            if marker in head:
                return content_type
        # The family is proven, only the member is not. The extension names it
        # — a claim, but a claim that can no longer smuggle in another format.
        extension = extension_of(filename)
        for content_type, extensions in ALLOWED_TYPES.items():
            if extension in extensions and content_type.startswith(
                "application/vnd.openxmlformats"
            ):
                return content_type
        raise UnsupportedFileTypeError("Unsupported Office Open XML type")

    raise UnsupportedFileTypeError(
        "ZIP archives are not accepted — upload the documents themselves"
    )


def _detect_text(head: bytes, filename: str) -> str:
    """Text has no signature, so it has to be recognised by being text.

    Which sort of text it is comes from the extension: `.csv` and `.txt` are
    the same bytes, and nothing in a file distinguishes them.
    """
    if not _is_text(head):
        raise UnsupportedFileTypeError("This file type is not accepted")

    sample = head.lstrip(codecs.BOM_UTF8).lstrip()
    if sample[:15].upper() == b"BEGIN:VCALENDAR":
        return "text/calendar"

    content_type = _TEXT_BY_EXTENSION.get(extension_of(filename))
    if content_type is None:
        raise UnsupportedFileTypeError("This file type is not accepted")
    if content_type == "text/calendar":
        # Named `.ics` without being one. Refused rather than filed as plain
        # text: a calendar that no calendar can read is a broken promise.
        raise UnsupportedFileTypeError("Not a valid iCalendar file")
    return content_type


def _is_text(head: bytes) -> bool:
    """UTF-8 (or ASCII) without control characters.

    Decoded incrementally so that a multi-byte character cut in half by the
    end of the sample is not mistaken for binary.
    """
    if b"\x00" in head:
        return False
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        text = decoder.decode(head, False)
    except UnicodeDecodeError:
        return False
    return not any((ord(char) < 32 and char not in "\t\r\n\f") or ord(char) == 127 for char in text)
