"""SEPA pain.008.001.02 direct debit XML generation for dues collection."""

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from xml.etree.ElementTree import Element, SubElement, tostring

PAIN_008_NAMESPACE = "urn:iso:std:iso:20022:tech:xsd:pain.008.001.02"

# Characters allowed in SEPA text fields (EPC best practice subset)
_SEPA_TEXT_RE = re.compile(r"[^A-Za-z0-9/\-?:().,'+ ]")

_GERMAN_TRANSLITERATION = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}
)


def sanitize_sepa_text(value: str, max_length: int = 70) -> str:
    """Transliterate umlauts and strip characters not allowed in SEPA fields."""
    value = value.translate(_GERMAN_TRANSLITERATION)
    value = _SEPA_TEXT_RE.sub(" ", value)
    value = " ".join(value.split())
    return value[:max_length]


@dataclass(frozen=True)
class SepaCreditor:
    name: str
    iban: str
    bic: str | None
    creditor_id: str


@dataclass(frozen=True)
class SepaPayment:
    end_to_end_id: str
    amount: Decimal
    debtor_name: str
    debtor_iban: str
    debtor_bic: str | None
    mandate_reference: str
    mandate_date: date
    remittance_info: str


def build_pain008(
    creditor: SepaCreditor,
    payments: list[SepaPayment],
    collection_date: date,
    message_id: str | None = None,
) -> str:
    """Build a pain.008.001.02 direct debit XML document (single batch, RCUR)."""
    message_id = message_id or f"unefy-{uuid.uuid4().hex[:27]}"
    total = sum((p.amount for p in payments), Decimal("0.00"))
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")

    root = Element("Document", {"xmlns": PAIN_008_NAMESPACE})
    cstmr = SubElement(root, "CstmrDrctDbtInitn")

    # Group header
    grp_hdr = SubElement(cstmr, "GrpHdr")
    SubElement(grp_hdr, "MsgId").text = message_id
    SubElement(grp_hdr, "CreDtTm").text = now
    SubElement(grp_hdr, "NbOfTxs").text = str(len(payments))
    SubElement(grp_hdr, "CtrlSum").text = f"{total:.2f}"
    initg_pty = SubElement(grp_hdr, "InitgPty")
    SubElement(initg_pty, "Nm").text = sanitize_sepa_text(creditor.name)

    # Payment info (one batch)
    pmt_inf = SubElement(cstmr, "PmtInf")
    SubElement(pmt_inf, "PmtInfId").text = f"{message_id}-1"
    SubElement(pmt_inf, "PmtMtd").text = "DD"
    SubElement(pmt_inf, "NbOfTxs").text = str(len(payments))
    SubElement(pmt_inf, "CtrlSum").text = f"{total:.2f}"

    pmt_tp_inf = SubElement(pmt_inf, "PmtTpInf")
    svc_lvl = SubElement(pmt_tp_inf, "SvcLvl")
    SubElement(svc_lvl, "Cd").text = "SEPA"
    lcl_instrm = SubElement(pmt_tp_inf, "LclInstrm")
    SubElement(lcl_instrm, "Cd").text = "CORE"
    SubElement(pmt_tp_inf, "SeqTp").text = "RCUR"

    SubElement(pmt_inf, "ReqdColltnDt").text = collection_date.isoformat()

    cdtr = SubElement(pmt_inf, "Cdtr")
    SubElement(cdtr, "Nm").text = sanitize_sepa_text(creditor.name)
    cdtr_acct = SubElement(pmt_inf, "CdtrAcct")
    cdtr_acct_id = SubElement(cdtr_acct, "Id")
    SubElement(cdtr_acct_id, "IBAN").text = creditor.iban.replace(" ", "")
    cdtr_agt = SubElement(pmt_inf, "CdtrAgt")
    fin_instn = SubElement(cdtr_agt, "FinInstnId")
    if creditor.bic:
        SubElement(fin_instn, "BIC").text = creditor.bic
    else:
        othr = SubElement(fin_instn, "Othr")
        SubElement(othr, "Id").text = "NOTPROVIDED"

    SubElement(pmt_inf, "ChrgBr").text = "SLEV"

    cdtr_schme_id = SubElement(pmt_inf, "CdtrSchmeId")
    schme_id = SubElement(cdtr_schme_id, "Id")
    prvt_id = SubElement(schme_id, "PrvtId")
    othr_id = SubElement(prvt_id, "Othr")
    SubElement(othr_id, "Id").text = creditor.creditor_id.replace(" ", "")
    schme_nm = SubElement(othr_id, "SchmeNm")
    SubElement(schme_nm, "Prtry").text = "SEPA"

    for payment in payments:
        tx = SubElement(pmt_inf, "DrctDbtTxInf")
        pmt_id = SubElement(tx, "PmtId")
        SubElement(pmt_id, "EndToEndId").text = payment.end_to_end_id
        SubElement(tx, "InstdAmt", {"Ccy": "EUR"}).text = f"{payment.amount:.2f}"

        drct_dbt_tx = SubElement(tx, "DrctDbtTx")
        mndt_rltd_inf = SubElement(drct_dbt_tx, "MndtRltdInf")
        SubElement(mndt_rltd_inf, "MndtId").text = sanitize_sepa_text(payment.mandate_reference, 35)
        SubElement(mndt_rltd_inf, "DtOfSgntr").text = payment.mandate_date.isoformat()

        dbtr_agt = SubElement(tx, "DbtrAgt")
        dbtr_fin = SubElement(dbtr_agt, "FinInstnId")
        if payment.debtor_bic:
            SubElement(dbtr_fin, "BIC").text = payment.debtor_bic
        else:
            othr = SubElement(dbtr_fin, "Othr")
            SubElement(othr, "Id").text = "NOTPROVIDED"

        dbtr = SubElement(tx, "Dbtr")
        SubElement(dbtr, "Nm").text = sanitize_sepa_text(payment.debtor_name)
        dbtr_acct = SubElement(tx, "DbtrAcct")
        dbtr_acct_id = SubElement(dbtr_acct, "Id")
        SubElement(dbtr_acct_id, "IBAN").text = payment.debtor_iban.replace(" ", "")

        rmt_inf = SubElement(tx, "RmtInf")
        SubElement(rmt_inf, "Ustrd").text = sanitize_sepa_text(payment.remittance_info, 140)

    xml_bytes: bytes = tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")
