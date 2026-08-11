"""Recognising a file by what is in it.

The end-to-end cases live in `test_library.py`; these are the corners that are
awkward to reach through an HTTP endpoint — a ZIP whose office format is
unknown, a UTF-8 character cut in half by the end of the sample, a `.ics` that
is not one.
"""

import io
import zipfile

import pytest

from app.core.file_types import UnsupportedFileTypeError, detect_content_type, extension_of


def _zip(entries: list[tuple[str, bytes]], *, first_stored: bool = False) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, (name, content) in enumerate(entries):
            archive.writestr(
                name,
                content,
                compress_type=(
                    zipfile.ZIP_STORED if first_stored and index == 0 else zipfile.ZIP_DEFLATED
                ),
            )
    return buffer.getvalue()


def test_a_pdf_is_a_pdf_whatever_it_is_called() -> None:
    assert detect_content_type(b"%PDF-1.4\n...", "urlaubsfoto.jpg") == "application/pdf"


def test_a_plain_archive_is_refused() -> None:
    """Not a document format — and the wrapper every macro-carrying file uses."""
    with pytest.raises(UnsupportedFileTypeError):
        detect_content_type(_zip([("a.txt", b"x")]), "protokoll.pdf")


def test_an_opendocument_says_what_it_is_inside_the_file() -> None:
    odt = _zip(
        [
            ("mimetype", b"application/vnd.oasis.opendocument.spreadsheet"),
            ("content.xml", b"<office/>"),
        ],
        first_stored=True,
    )

    assert detect_content_type(odt, "kasse.ods") == "application/vnd.oasis.opendocument.spreadsheet"


def test_an_unknown_opendocument_type_is_refused() -> None:
    """`.odg`, `.odf` and friends are not on the list, and the file says so."""
    odg = _zip(
        [
            ("mimetype", b"application/vnd.oasis.opendocument.graphics"),
            ("content.xml", b"<office/>"),
        ],
        first_stored=True,
    )

    with pytest.raises(UnsupportedFileTypeError):
        detect_content_type(odg, "zeichnung.odg")


def test_an_ooxml_file_is_recognised_by_its_entry_paths() -> None:
    xlsx = _zip([("[Content_Types].xml", b"<Types/>"), ("xl/workbook.xml", b"<w/>")])

    assert (
        detect_content_type(xlsx, "beitraege.xlsx")
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_an_ooxml_file_without_a_telling_path_falls_back_to_its_name() -> None:
    """The family is proven by the bytes; only which member it is comes from
    the extension, and a wrong one can no longer smuggle in another format."""
    bare = _zip([("[Content_Types].xml", b"<Types/>"), ("docProps/app.xml", b"<a/>")])

    assert (
        detect_content_type(bare, "vorlage.pptx")
        == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    with pytest.raises(UnsupportedFileTypeError):
        detect_content_type(bare, "vorlage.zip")


def test_text_is_told_apart_by_its_name_because_nothing_else_can() -> None:
    assert detect_content_type(b"a;b;c\n1;2;3\n", "liste.csv") == "text/csv"
    assert detect_content_type(b"a;b;c\n1;2;3\n", "liste.txt") == "text/plain"


def test_an_unknown_text_extension_is_not_accepted() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        detect_content_type(b"# Notizen\n", "notizen.md")


def test_a_calendar_is_recognised_from_its_first_line() -> None:
    assert detect_content_type(b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n", "termine.ics")


def test_something_named_ics_that_is_not_a_calendar_is_refused() -> None:
    """Filing it as plain text would leave a calendar no calendar can read."""
    with pytest.raises(UnsupportedFileTypeError):
        detect_content_type(b"nur eine Notiz\n", "termine.ics")


def test_a_byte_order_mark_does_not_hide_a_calendar() -> None:
    assert detect_content_type(b"\xef\xbb\xbfBEGIN:VCALENDAR\r\n", "termine.ics") == "text/calendar"


def test_a_character_cut_in_half_by_the_sample_is_still_text() -> None:
    """The head is the first 8 KB, and a multi-byte character straddles it."""
    head = "Beiträge".encode()[:-1]  # ß split down the middle

    assert detect_content_type(head, "notiz.txt") == "text/plain"


def test_binary_rubbish_is_not_text() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        detect_content_type(b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 32, "tool.txt")


def test_an_empty_file_is_refused() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        detect_content_type(b"", "leer.pdf")


def test_an_extension_is_read_as_a_name_not_a_path() -> None:
    assert extension_of("C:\\Users\\vorstand\\Satzung.PDF") == ".pdf"
    assert extension_of("satzung") == ""
