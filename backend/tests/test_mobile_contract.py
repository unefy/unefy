"""The committed mobile contract must match the models it is derived from.

This is one half of the drift guard the mobile CLAUDE.md asks for; the other
half lives in the Android JVM tests, which validate the hand-written DTOs
against the committed file. Together: a schema change here fails a build
somewhere, instead of surfacing as a runtime decoding error on a phone.
"""

import json
from pathlib import Path

from scripts.export_mobile_contract import build_contract

CONTRACT = Path(__file__).resolve().parent.parent.parent / "docs" / "api" / "mobile-contract.json"


def test_the_committed_contract_matches_the_models() -> None:
    committed = json.loads(CONTRACT.read_text())

    assert committed == build_contract(), (
        "docs/api/mobile-contract.json is stale. A response schema changed - "
        "regenerate with `uv run python scripts/export_mobile_contract.py`, "
        "commit the file, and expect the Android DTO tests to tell you whether "
        "the apps care."
    )
