"""Writes the contract the hand-written mobile DTOs are validated against.

The mobile CLAUDE.md wants the DTOs checked against "the OpenAPI spec" — but
the routes return plain dicts, so the generated spec carries almost no
response schemas to check against. This exports the same truth one level
deeper: the Pydantic response models themselves, as
`docs/api/mobile-contract.json`.

Per schema: every field with whether it may be null. That is exactly what a
hand-written DTO can get wrong in a way that only explodes at runtime — a
renamed field silently decodes to its default, and a non-nullable DTO field
for a nullable server field throws mid-parse (the dues mirror stayed empty
for precisely that once).

The file is committed; `tests/test_mobile_contract.py` fails when it drifts
from the models, and the Android JVM tests fail when a DTO drifts from the
file. Backend drift therefore breaks a build instead of a phone.

Run: uv run python scripts/export_mobile_contract.py
"""

import json
from pathlib import Path
from typing import Any

from app.schemas.consent import ConsentEntry, ConsentOverview, ConsentState
from app.schemas.competition import (
    CompetitionResponse,
    EntryDetails,
    EntryResponse,
    ScoreboardRow,
    SessionResponse,
    ShotDetail,
)
from app.schemas.document import IssuedDocumentResponse, TemplateResponse
from app.schemas.due import DueResponse, DueSummaryResponse
from app.schemas.function import MemberFunctionResponse
from app.schemas.event import EventRegistrationResponse, EventResponse
from app.schemas.member import (
    FederationMembershipResponse,
    MemberDirectoryEntry,
    MemberResponse,
)
from app.schemas.sync import SyncMeta, Tombstone
from app.schemas.target_type import CaliberResponse, TargetTypeResponse

#: What the mobile apps decode. Enrichment fields are the ones the list
#: endpoints merge in beside the model (they exist in no schema, which is why
#: they are spelled out here rather than derived).
SCHEMAS: dict[str, Any] = {
    "MemberResponse": MemberResponse,
    "MemberDirectoryEntry": MemberDirectoryEntry,
    "FederationMembershipResponse": FederationMembershipResponse,
    "MemberFunctionResponse": MemberFunctionResponse,
    "ConsentState": ConsentState,
    "ConsentEntry": ConsentEntry,
    "ConsentOverview": ConsentOverview,
    "IssuedDocumentResponse": IssuedDocumentResponse,
    "TemplateResponse": TemplateResponse,
    "EventResponse": EventResponse,
    "EventRegistrationResponse": EventRegistrationResponse,
    "DueResponse": DueResponse,
    "DueSummaryResponse": DueSummaryResponse,
    "CompetitionResponse": CompetitionResponse,
    "SessionResponse": SessionResponse,
    "EntryResponse": EntryResponse,
    # Not a response model of its own — the shape inside `EntryResponse.details`,
    # which is an untyped JSONB dict on the wire. Exported so the Android DTO for
    # the shot list is checked like everything else.
    "EntryDetails": EntryDetails,
    "ShotDetail": ShotDetail,
    "TargetTypeResponse": TargetTypeResponse,
    "CaliberResponse": CaliberResponse,
    "ScoreboardRow": ScoreboardRow,
    "SyncMeta": SyncMeta,
    "Tombstone": Tombstone,
}

#: Fields the list endpoints merge in as plain dict keys — see
#: `app/api/v1/events.py` and `app/api/v1/dues.py`. All nullable/defaulted by
#: construction: they are absent from the sync payloads.
ENRICHMENT: dict[str, dict[str, bool]] = {
    "EventResponse": {
        "is_registered": True,
        "registered_count": True,
        "competition_name": True,
        # Detail-endpoint only: the merge always writes a list, never null;
        # the list and sync payloads simply omit it.
        "registrations": False,
        # Detail-endpoint only, board only — members get an empty list.
        "attendance_sessions": False,
    },
    "DueResponse": {"member_name": True},
    "EventRegistrationResponse": {"member_name": True},
}

CONTRACT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "api"


def build_contract() -> dict[str, Any]:
    contract: dict[str, Any] = {}
    for name, model in sorted(SCHEMAS.items()):
        schema = model.model_json_schema()
        required = set(schema.get("required", []))
        fields: dict[str, dict[str, bool]] = {}
        for field, spec in schema.get("properties", {}).items():
            nullable = _nullable(spec) or field not in required
            fields[field] = {"nullable": nullable}
        for field, nullable in ENRICHMENT.get(name, {}).items():
            fields[field] = {"nullable": nullable}
        contract[name] = {"fields": dict(sorted(fields.items()))}
    return contract


def _nullable(spec: dict[str, Any]) -> bool:
    """Whether the JSON value may be an explicit null."""
    if spec.get("type") == "null":
        return True
    variants = [v for v in spec.get("anyOf", []) if isinstance(v, dict)]
    return any(variant.get("type") == "null" for variant in variants)


def main() -> None:
    CONTRACT_PATH.mkdir(parents=True, exist_ok=True)
    target = CONTRACT_PATH / "mobile-contract.json"
    target.write_text(json.dumps(build_contract(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
