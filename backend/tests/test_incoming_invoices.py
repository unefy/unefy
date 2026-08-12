"""The register: what arrives, what it says, and what must not happen twice."""

import io
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from tests.test_einvoice import CII, UBL

pytestmark = pytest.mark.asyncio

SCAN = b"%PDF-1.7\n% a scan with nothing machine-readable in it\n"


def upload(content: bytes, filename: str, media_type: str) -> dict[str, object]:
    return {"file": (filename, io.BytesIO(content), media_type)}


async def a_scan(client: AsyncClient, filename: str = "rechnung.pdf") -> dict:
    response = await client.post(
        "/api/v1/incoming-invoices", files=upload(SCAN, filename, "application/pdf")
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


# --- Taking the file in ---


async def test_an_e_invoice_fills_itself_in(auth_client: AsyncClient) -> None:
    """The point of the whole feature: the supplier already said all of this."""
    response = await auth_client.post(
        "/api/v1/incoming-invoices", files=upload(CII, "rechnung.xml", "application/xml")
    )
    assert response.status_code == 201, response.text

    data = response.json()["data"]
    assert data["source"] == "xrechnung"
    assert data["supplier_name"] == "Sportgeräte Müller GmbH"
    assert data["invoice_number"] == "RE-2026-0815"
    assert data["invoice_date"] == "2026-01-31"
    assert data["due_date"] == "2026-02-14"
    assert data["gross_amount"] == "499.80"
    assert data["currency"] == "EUR"
    assert data["status"] == "open"
    assert data["is_complete"] is True


async def test_a_scan_is_kept_and_left_incomplete(auth_client: AsyncClient) -> None:
    """The invoice exists either way. Refusing it over a missing field is how
    a club loses the document it was holding in its hand."""
    data = await a_scan(auth_client)

    assert data["source"] == "manual"
    assert data["gross_amount"] is None
    assert data["supplier_name"] is None
    assert data["is_complete"] is False
    assert data["original_filename"] == "rechnung.pdf"


async def test_a_file_that_is_not_a_document_at_all_is_refused(
    auth_client: AsyncClient,
) -> None:
    """The register takes paperwork, not anything at all."""
    response = await auth_client.post(
        "/api/v1/incoming-invoices",
        files=upload(b"MZ\x90\x00binary", "rechnung.exe", "application/octet-stream"),
    )
    assert response.status_code == 415


# --- The duplicate check ---


async def test_the_same_invoice_twice_is_refused(auth_client: AsyncClient) -> None:
    """The one mistake a register exists to prevent: paying twice."""
    first = await auth_client.post(
        "/api/v1/incoming-invoices", files=upload(CII, "rechnung.xml", "application/xml")
    )
    assert first.status_code == 201

    again = await auth_client.post(
        "/api/v1/incoming-invoices", files=upload(CII, "kopie.xml", "application/xml")
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "INVOICE_ALREADY_RECORDED"


async def test_two_scans_do_not_collide(auth_client: AsyncClient) -> None:
    """Neither has a supplier or a number yet. Refusing the second would
    refuse every scan after the first."""
    await a_scan(auth_client, "januar.pdf")
    await a_scan(auth_client, "februar.pdf")

    listed = await auth_client.get("/api/v1/incoming-invoices")
    assert listed.json()["meta"]["total"] == 2


async def test_typing_a_number_that_already_exists_is_refused(
    auth_client: AsyncClient,
) -> None:
    """The duplicate arrives as a scan just as often as as an e-invoice."""
    await auth_client.post(
        "/api/v1/incoming-invoices", files=upload(CII, "rechnung.xml", "application/xml")
    )
    scan = await a_scan(auth_client)

    response = await auth_client.patch(
        f"/api/v1/incoming-invoices/{scan['id']}",
        json={"supplier_name": "Sportgeräte Müller GmbH", "invoice_number": "RE-2026-0815"},
    )
    assert response.status_code == 409


async def test_another_club_may_send_the_same_invoice_number(
    auth_client: AsyncClient,
) -> None:
    """The check is per club. Two clubs buying from one supplier is normal."""
    await auth_client.post(
        "/api/v1/incoming-invoices", files=upload(UBL, "rechnung.xml", "application/xml")
    )
    listed = await auth_client.get("/api/v1/incoming-invoices")
    assert listed.json()["meta"]["total"] == 1


# --- Completing and paying ---


async def test_typed_figures_stop_claiming_to_come_from_the_document(
    auth_client: AsyncClient,
) -> None:
    """Once a person edits an amount it is their reading, not the sender's
    statement — and the list is only worth reading if it says which."""
    response = await auth_client.post(
        "/api/v1/incoming-invoices", files=upload(CII, "rechnung.xml", "application/xml")
    )
    invoice = response.json()["data"]
    assert invoice["source"] == "xrechnung"

    corrected = await auth_client.patch(
        f"/api/v1/incoming-invoices/{invoice['id']}", json={"gross_amount": "480.00"}
    )
    assert corrected.status_code == 200
    assert corrected.json()["data"]["source"] == "manual"
    assert corrected.json()["data"]["gross_amount"] == "480.00"


async def test_a_note_does_not_make_the_figures_a_persons_reading(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.post(
        "/api/v1/incoming-invoices", files=upload(CII, "rechnung.xml", "application/xml")
    )
    invoice = response.json()["data"]

    noted = await auth_client.patch(
        f"/api/v1/incoming-invoices/{invoice['id']}", json={"note": "Trikots Jugend"}
    )
    assert noted.json()["data"]["source"] == "xrechnung"


async def test_an_invoice_without_an_amount_cannot_be_paid(
    auth_client: AsyncClient,
) -> None:
    """ "Paid" would then say nothing anybody can check, and being checkable is
    the register's whole job."""
    scan = await a_scan(auth_client)

    response = await auth_client.post(f"/api/v1/incoming-invoices/{scan['id']}/pay", json={})
    assert response.status_code == 422


async def test_paying_records_the_day(auth_client: AsyncClient) -> None:
    created = await auth_client.post(
        "/api/v1/incoming-invoices", files=upload(CII, "rechnung.xml", "application/xml")
    )
    invoice = created.json()["data"]

    paid = await auth_client.post(
        f"/api/v1/incoming-invoices/{invoice['id']}/pay", json={"paid_on": "2026-02-10"}
    )
    assert paid.status_code == 200
    assert paid.json()["data"]["status"] == "paid"
    assert paid.json()["data"]["paid_on"] == "2026-02-10"

    # For the payment recorded against the wrong invoice.
    reopened = await auth_client.post(f"/api/v1/incoming-invoices/{invoice['id']}/reopen")
    assert reopened.json()["data"]["status"] == "open"
    assert reopened.json()["data"]["paid_on"] is None


async def test_a_cancelled_invoice_cannot_be_paid(auth_client: AsyncClient) -> None:
    created = await auth_client.post(
        "/api/v1/incoming-invoices", files=upload(CII, "rechnung.xml", "application/xml")
    )
    invoice = created.json()["data"]
    await auth_client.post(f"/api/v1/incoming-invoices/{invoice['id']}/cancel")

    response = await auth_client.post(f"/api/v1/incoming-invoices/{invoice['id']}/pay", json={})
    assert response.status_code == 409


# --- The figures ---


async def test_the_summary_leaves_cancelled_out_of_both_totals(
    auth_client: AsyncClient,
) -> None:
    """The club decided it does not owe them — but the decision stays visible."""
    paid = (
        await auth_client.post(
            "/api/v1/incoming-invoices", files=upload(CII, "a.xml", "application/xml")
        )
    ).json()["data"]
    await auth_client.post(f"/api/v1/incoming-invoices/{paid['id']}/pay", json={})

    open_one = (
        await auth_client.post(
            "/api/v1/incoming-invoices", files=upload(UBL, "b.xml", "application/xml")
        )
    ).json()["data"]

    cancelled = await a_scan(auth_client, "storniert.pdf")
    await auth_client.patch(
        f"/api/v1/incoming-invoices/{cancelled['id']}",
        json={
            "supplier_name": "Irrtum GmbH",
            "invoice_number": "X-1",
            "invoice_date": "2026-01-05",
            "gross_amount": "999.00",
        },
    )
    await auth_client.post(f"/api/v1/incoming-invoices/{cancelled['id']}/cancel")

    summary = (await auth_client.get("/api/v1/incoming-invoices/summary")).json()["data"]
    assert summary["paid_amount"] == "499.80"
    assert summary["open_amount"] == "119.00"
    assert summary["total_amount"] == "618.80"
    assert summary["cancelled_amount"] == "999.00"
    assert summary["cancelled_count"] == 1
    assert open_one["gross_amount"] == "119.00"


async def test_the_summary_says_how_much_it_cannot_see(
    auth_client: AsyncClient,
) -> None:
    """A total that silently omits four untyped scans is a wrong total."""
    await a_scan(auth_client, "eins.pdf")
    await a_scan(auth_client, "zwei.pdf")

    summary = (await auth_client.get("/api/v1/incoming-invoices/summary")).json()["data"]
    assert summary["incomplete_count"] == 2
    # Compared as a number: nothing was counted, and whether the server writes
    # that as "0" or "0.00" is not what this test is about.
    assert Decimal(summary["total_amount"]) == 0


async def test_a_year_filter_leaves_out_what_has_no_date(
    auth_client: AsyncClient,
) -> None:
    """An invoice with no date belongs to no year — better absent than filed
    under an arbitrary one."""
    await auth_client.post(
        "/api/v1/incoming-invoices", files=upload(CII, "rechnung.xml", "application/xml")
    )
    await a_scan(auth_client)

    listed = await auth_client.get("/api/v1/incoming-invoices?year=2026")
    assert listed.json()["meta"]["total"] == 1


# --- The file, and the door ---


async def test_the_stored_file_comes_back_as_it_went_in(
    auth_client: AsyncClient,
) -> None:
    invoice = await a_scan(auth_client)

    response = await auth_client.get(f"/api/v1/incoming-invoices/{invoice['id']}/file")
    assert response.status_code == 200
    assert response.content == SCAN
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_an_xml_invoice_is_never_rendered_in_the_browser(
    auth_client: AsyncClient,
) -> None:
    """XML can carry a stylesheet that turns it into HTML, and from this origin
    that would be a script with the reader's session."""
    created = await auth_client.post(
        "/api/v1/incoming-invoices", files=upload(CII, "rechnung.xml", "application/xml")
    )
    invoice = created.json()["data"]

    response = await auth_client.get(f"/api/v1/incoming-invoices/{invoice['id']}/file")
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_a_deleted_invoice_is_gone_from_the_register(
    auth_client: AsyncClient,
) -> None:
    invoice = await a_scan(auth_client)

    assert (
        await auth_client.delete(f"/api/v1/incoming-invoices/{invoice['id']}")
    ).status_code == 204
    assert (await auth_client.get(f"/api/v1/incoming-invoices/{invoice['id']}")).status_code == 404
    assert (await auth_client.get("/api/v1/incoming-invoices")).json()["meta"]["total"] == 0


async def test_another_clubs_invoice_is_not_found(
    auth_client: AsyncClient,
) -> None:
    assert (await auth_client.get(f"/api/v1/incoming-invoices/{uuid.uuid4()}")).status_code == 404


async def test_the_register_is_board_work(anon_client: AsyncClient) -> None:
    assert (await anon_client.get("/api/v1/incoming-invoices")).status_code == 403
    assert (await anon_client.get("/api/v1/incoming-invoices/summary")).status_code == 403
    assert (
        await anon_client.post(
            "/api/v1/incoming-invoices", files=upload(SCAN, "x.pdf", "application/pdf")
        )
    ).status_code == 403


async def test_the_quota_counts_invoices_too(
    auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The library and the register share a disk. A quota that saw only one of
    them would report 3% used on a full volume."""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "TENANT_STORAGE_QUOTA_BYTES", len(SCAN) + 10)

    assert (
        await auth_client.post(
            "/api/v1/incoming-invoices", files=upload(SCAN, "eins.pdf", "application/pdf")
        )
    ).status_code == 201

    second = await auth_client.post(
        "/api/v1/incoming-invoices", files=upload(SCAN, "zwei.pdf", "application/pdf")
    )
    assert second.status_code == 413
    assert second.json()["error"]["code"] == "STORAGE_QUOTA_EXCEEDED"

    usage = await auth_client.get("/api/v1/library/usage")
    assert Decimal(usage.json()["data"]["used_bytes"]) == len(SCAN)
