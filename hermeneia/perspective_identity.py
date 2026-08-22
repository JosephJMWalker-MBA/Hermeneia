"""Governed Perspective frame-v2 identity helpers.

ADR-0045 separates frame semantics from declaration/revision occurrence.
The frame fingerprint says what the Perspective means; the Perspective ID says
which immutable human-declared canonical node entered the record.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .perspective_runs import (
    PerspectiveDefinition,
    PerspectiveResolution,
    normalize_transient_perspective_draft,
    transient_perspective_fingerprint,
    transient_perspective_semantics,
)


FRAME_V2_SCHEME = "perspective-frame-v2"
LEGACY_SCHEME = "perspective-label-v1"
SAVED_PERSPECTIVE_ORIGIN = "canonical_saved"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_declared_by(value: Any) -> str:
    declared_by = str(value or "").strip()
    if not declared_by:
        raise ValueError("declared_by is required")
    return declared_by


def normalize_revision_reason(value: Any) -> str:
    reason = str(value or "").strip()
    if not reason:
        raise ValueError("revision reason is required")
    return reason


def _canonical_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def perspective_frame_v2_id(
    *,
    definition_fingerprint: str,
    declared_by: str,
    predecessor_perspective_id: str | None = None,
) -> str:
    context: dict[str, object]
    if predecessor_perspective_id:
        context = {
            "kind": "revision",
            "predecessor_perspective_id": predecessor_perspective_id,
            "declared_by": normalize_declared_by(declared_by),
        }
    else:
        context = {
            "kind": "root",
            "declared_by": normalize_declared_by(declared_by),
        }
    payload = {
        "identity_scheme": FRAME_V2_SCHEME,
        "definition_fingerprint": definition_fingerprint,
        "declaration_context": context,
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{FRAME_V2_SCHEME}:{digest}"


def frame_v2_row_from_draft(
    draft: dict[str, Any],
    *,
    declared_by: Any,
    declared_date: str,
    predecessor_perspective_id: str | None = None,
) -> tuple[dict[str, object], PerspectiveResolution]:
    declared_by_clean = normalize_declared_by(declared_by)
    if not str(declared_date or "").strip():
        raise ValueError("declared_date is required")
    resolution = normalize_transient_perspective_draft(draft)
    definition = resolution.definition
    fingerprint = transient_perspective_fingerprint(definition)
    perspective_id = perspective_frame_v2_id(
        definition_fingerprint=fingerprint,
        declared_by=declared_by_clean,
        predecessor_perspective_id=predecessor_perspective_id,
    )
    semantics = transient_perspective_semantics(definition)
    row = {
        "id": perspective_id,
        "name": definition.label,
        "description": definition.purpose,
        "created_at": declared_date,
        "identity_scheme": FRAME_V2_SCHEME,
        "definition_fingerprint": fingerprint,
        "purpose": definition.purpose,
        "questions_json": _canonical_json({"items": semantics["questions"]}),
        "challenges_json": _canonical_json({"items": semantics["challenges"]}),
        "limitations_json": _canonical_json({"items": semantics["limitations"]}),
        "declared_by": declared_by_clean,
        "declared_date": declared_date,
    }
    return row, resolution


def _json_items(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    parsed = json.loads(value) if isinstance(value, str) else value
    if isinstance(parsed, dict):
        parsed = parsed.get("items")
    if not isinstance(parsed, list):
        return ()
    return tuple(str(item) for item in parsed)


def definition_from_frame_v2_row(row: dict[str, Any]) -> PerspectiveDefinition:
    if row.get("identity_scheme") != FRAME_V2_SCHEME:
        raise ValueError("saved Perspective is not frame-v2")
    return PerspectiveDefinition(
        id=str(row["id"]),
        version="1",
        label=str(row["name"]),
        purpose=str(row["purpose"] or ""),
        questions=_json_items(row.get("questions_json")),
        challenges=_json_items(row.get("challenges_json")),
        limitations=_json_items(row.get("limitations_json")),
    )


def frame_v2_payload(row: dict[str, Any]) -> dict[str, object]:
    definition = definition_from_frame_v2_row(row)
    return {
        "id": row["id"],
        "identity_scheme": row["identity_scheme"],
        "definition_fingerprint": row["definition_fingerprint"],
        "label": definition.label,
        "purpose": definition.purpose,
        "questions": list(definition.questions),
        "challenges": list(definition.challenges),
        "limitations": list(definition.limitations),
        "declared_by": row["declared_by"],
        "declared_date": row["declared_date"],
        "created_at": row["created_at"],
        "is_current_leaf": bool(row.get("is_current_leaf", 1)),
    }


def resolution_from_frame_v2_row(row: dict[str, Any]) -> PerspectiveResolution:
    definition = definition_from_frame_v2_row(row)
    metadata = {
        "origin": SAVED_PERSPECTIVE_ORIGIN,
        "perspective_id": row["id"],
        "identity_scheme": row["identity_scheme"],
        "definition_fingerprint": row["definition_fingerprint"],
        "definition": transient_perspective_semantics(definition),
        "declared_by": row["declared_by"],
        "declared_date": row["declared_date"],
    }
    return PerspectiveResolution(definition=definition, receipt_metadata=metadata)
