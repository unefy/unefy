"""The figures a club reads out once a year, and the file it pastes them from."""

import csv
import io
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.dependencies import AuthContext, require_role
from app.schemas.report import AnnualReport
from app.services.report import ReportService

router = APIRouter()

#: German spreadsheets. `;` as the separator and `,` as the decimal mark,
#: because that is what Excel on a German locale reads without being asked —
#: a comma-separated file with dotted decimals lands in one column, and the
#: treasurer who opens it has no reason to know why.
CSV_DELIMITER = ";"

#: Excel decides an ASCII file is Latin-1 and renders "Beiträge" as "BeitrÃ¤ge".
#: The byte-order mark is what makes it read UTF-8 instead.
UTF8_BOM = "﻿"


@router.get("/annual")
async def annual_report(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> dict[str, Any]:
    """Membership, dues and attendance for one calendar year.

    One call for all three: they are read together, they are printed together,
    and three round trips would only let them disagree about which year they
    are showing.
    """
    service = ReportService(session, auth.tenant)
    report = await service.annual(year or await service.current_year())
    return {"data": AnnualReport.model_validate(report).model_dump(mode="json")}


@router.get("/annual/export")
async def export_annual_report(
    auth: AuthContext = Depends(require_role("owner", "admin", "board")),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> Response:
    """The same figures as a spreadsheet.

    One file with the three blocks under each other rather than three
    downloads: what the club does with this is paste it into a report, and
    three files means three chances to paste last year's by mistake.
    """
    service = ReportService(session, auth.tenant)
    reporting_year = year or await service.current_year()
    report = await service.annual(reporting_year)

    buffer = io.StringIO()
    buffer.write(UTF8_BOM)
    writer = csv.writer(buffer, delimiter=CSV_DELIMITER, lineterminator="\r\n")
    _write_membership(writer, report["membership"])
    writer.writerow([])
    _write_dues(writer, report["dues"])
    writer.writerow([])
    _write_attendance(writer, report["attendance"])

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="jahresbericht-{reporting_year}.csv"',
            "Cache-Control": "no-store",
        },
    )


def _write_membership(writer: Any, data: dict[str, Any]) -> None:
    writer.writerow(["Mitgliederentwicklung", data["year"]])
    writer.writerow(["Bestand am Jahresanfang", data["opening"]])
    writer.writerow(["Eintritte", data["joined"]])
    writer.writerow(["Austritte", data["left"]])
    writer.writerow(["Bestand am Jahresende", data["closing"]])

    writer.writerow([])
    writer.writerow(["Kategorie", "Anzahl"])
    for row in data["by_category"]:
        writer.writerow([row["value"] or "ohne Angabe", row["count"]])

    writer.writerow([])
    writer.writerow(["Altersgruppe", "Anzahl"])
    for row in data["by_age_band"]:
        writer.writerow([AGE_BAND_LABELS.get(row["band"], row["band"]), row["count"]])
    if data["without_birthday"]:
        writer.writerow(["ohne Geburtsdatum", data["without_birthday"]])


def _write_dues(writer: Any, data: dict[str, Any]) -> None:
    writer.writerow(["Beiträge", data["year"]])
    writer.writerow(["Beitragsart", "Anzahl", "Soll", "Ist", "Offen", "Storniert"])
    for row in data["by_fee"]:
        writer.writerow(
            [
                row["fee_name"],
                row["count"],
                _money(row["charged"]),
                _money(row["paid"]),
                _money(row["open"]),
                _money(row["cancelled"]),
            ]
        )
    totals = data["totals"]
    writer.writerow(
        [
            "Summe",
            totals["count"],
            _money(totals["charged"]),
            _money(totals["paid"]),
            _money(totals["open"]),
            _money(totals["cancelled"]),
        ]
    )


def _write_attendance(writer: Any, data: dict[str, Any]) -> None:
    writer.writerow(["Anwesenheit", data["year"]])
    writer.writerow(["Einheiten", data["sessions"]])
    writer.writerow(["Besuche", data["records"]])
    writer.writerow(["Mitglieder", data["members"]])
    writer.writerow(["Gäste", data["guests"]])
    writer.writerow(["davon selbst geführt", data["self_kept"]])
    if data["average_per_session"] is not None:
        writer.writerow(["Schnitt je Einheit", _number(data["average_per_session"])])

    writer.writerow([])
    writer.writerow(["Monat", "Besuche"])
    for row in data["by_month"]:
        writer.writerow([MONTHS[row["month"] - 1], row["count"]])


def _money(value: Decimal | str) -> str:
    """Two places and a decimal comma — see [CSV_DELIMITER]."""
    return f"{Decimal(value):.2f}".replace(".", ",")


def _number(value: float | str) -> str:
    return str(value).replace(".", ",")


AGE_BAND_LABELS = {
    "under_18": "unter 18",
    "18_to_26": "18 bis 26",
    "27_to_40": "27 bis 40",
    "41_to_60": "41 bis 60",
    "over_60": "über 60",
}

MONTHS = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)
