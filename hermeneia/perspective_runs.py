"""Transient Perspective Run primitives.

A Perspective Run is inquiry-time assistance. It binds a frame, an explicit
scope receipt, a human question, and an execution identity, then returns a
proposed reading. It does not create a canonical Interpretation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PerspectiveDefinition:
    """Built-in interpretive frame data.

    Perspective identity is frame semantics only. Provider, model, style,
    audience, voice, and output controls belong to execution/configuration
    layers outside this object.
    """

    id: str
    version: str
    label: str
    purpose: str
    questions: tuple[str, ...]
    challenges: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PerspectiveResolution:
    definition: PerspectiveDefinition
    receipt_metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class RoomParticipantResolution:
    ordinal: int
    participant_kind: str
    definition: PerspectiveDefinition
    receipt_metadata: dict[str, object] | None = None


PERSPECTIVE_DEFINITIONS: tuple[PerspectiveDefinition, ...] = (
    PerspectiveDefinition(
        id="close-reader",
        version="1",
        label="Close Reader",
        purpose=(
            "Examine what the selected evidence itself supports before "
            "importing broader explanation."
        ),
        questions=(
            "What words, images, or relationships are doing the work?",
            "What tension or distinction is easy to overlook?",
            "What can actually be supported from this material?",
        ),
        challenges=(
            "Stay close to the supplied passage.",
            "Name uncertainty instead of smoothing it away.",
            "Do not import context that was not supplied in the Scope.",
        ),
        limitations=(
            "Deliberately narrow.",
            "May miss external context.",
        ),
    ),
    PerspectiveDefinition(
        id="contextual-reader",
        version="1",
        label="Contextual Reader",
        purpose=(
            "Examine how relevant literary, historical, conceptual, or "
            "investigation context may illuminate the evidence without "
            "overriding it."
        ),
        questions=(
            "What context changes how this passage might be understood?",
            "Which contextual claim is actually supported?",
            "What uncertainty remains?",
        ),
        challenges=(
            "Separate source evidence from contextual inference.",
            "Do not let context override the supplied passage.",
            "Identify where the Scope is too narrow to support a claim.",
        ),
        limitations=(
            "Context can encourage overreach.",
            "Requires careful separation of evidence and inference.",
        ),
    ),
    PerspectiveDefinition(
        id="skeptical-reader",
        version="1",
        label="Skeptical Reader",
        purpose=(
            "Stress-test the current reading for unsupported assumptions, "
            "inflated certainty, missing alternatives, and contradictory evidence."
        ),
        questions=(
            "What is being assumed?",
            "What competing reading remains plausible?",
            "What evidence would weaken this interpretation?",
        ),
        challenges=(
            "Challenge unsupported certainty.",
            "Preserve plausible alternatives.",
            "Do not confuse skepticism with automatic rejection.",
        ),
        limitations=(
            "May understate a well-supported reading.",
            "Skepticism is not automatic rejection.",
        ),
    ),
)

DEFAULT_ROOM_PERSPECTIVES: tuple[str, ...] = (
    "close-reader",
    "contextual-reader",
    "skeptical-reader",
)

TRANSIENT_PERSPECTIVE_ORIGIN = "user_authored_transient"
TRANSIENT_PERSPECTIVE_VERSION = "draft"
_TRANSIENT_ALLOWED_FIELDS = {
    "label",
    "name",
    "purpose",
    "questions",
    "challenges",
    "limitations",
}
_TRANSIENT_FORBIDDEN_FIELDS = {
    "provider",
    "provider_id",
    "model",
    "model_id",
    "temperature",
    "top_p",
    "inference_configuration",
    "execution_config",
    "audience",
    "tone",
    "voice",
    "writing_style",
    "style",
    "output_language",
    "language",
    "output_format",
    "rhetorical_style",
}


def perspective_definition(perspective_id: str) -> PerspectiveDefinition | None:
    for definition in PERSPECTIVE_DEFINITIONS:
        if definition.id == perspective_id:
            return definition
    return None


def perspective_definitions_payload() -> list[dict[str, object]]:
    return [definition.to_dict() for definition in PERSPECTIVE_DEFINITIONS]


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _clean_frame_items(value: Any, *, field: str, required: bool) -> tuple[str, ...]:
    if isinstance(value, str):
        raw_items = value.splitlines()
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []
    items = tuple(str(item).strip() for item in raw_items if str(item).strip())
    if required and not items:
        raise ValueError(f"Transient Perspective {field} require at least one item.")
    if len(items) > 12:
        raise ValueError(f"Transient Perspective {field} may contain at most 12 items.")
    for item in items:
        if len(item) > 500:
            raise ValueError(f"Transient Perspective {field} items must be 500 characters or fewer.")
    return items


def transient_perspective_semantics(definition: PerspectiveDefinition) -> dict[str, object]:
    return {
        "label": definition.label,
        "purpose": definition.purpose,
        "questions": list(definition.questions),
        "challenges": list(definition.challenges),
        "limitations": list(definition.limitations),
    }


def transient_perspective_fingerprint(definition: PerspectiveDefinition) -> str:
    payload = json.dumps(
        transient_perspective_semantics(definition),
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def normalize_transient_perspective_draft(draft: dict[str, Any]) -> PerspectiveResolution:
    if not isinstance(draft, dict):
        raise ValueError("Transient Perspective draft is required.")
    for field, value in draft.items():
        if field not in _TRANSIENT_ALLOWED_FIELDS:
            if field in _TRANSIENT_FORBIDDEN_FIELDS or value not in (None, "", [], {}):
                raise ValueError(f"Unsupported Perspective field: {field}")
    label = _clean_text(draft.get("label") or draft.get("name"))
    purpose = _clean_text(draft.get("purpose"))
    if not label:
        raise ValueError("Transient Perspective name is required.")
    if len(label) > 80:
        raise ValueError("Transient Perspective name must be 80 characters or fewer.")
    if not purpose:
        raise ValueError("Transient Perspective purpose is required.")
    if len(purpose) > 1000:
        raise ValueError("Transient Perspective purpose must be 1000 characters or fewer.")
    questions = _clean_frame_items(draft.get("questions"), field="questions", required=True)
    challenges = _clean_frame_items(draft.get("challenges"), field="challenges", required=False)
    limitations = _clean_frame_items(draft.get("limitations"), field="limitations", required=False)
    definition = PerspectiveDefinition(
        id="transient:pending",
        version=TRANSIENT_PERSPECTIVE_VERSION,
        label=label,
        purpose=purpose,
        questions=questions,
        challenges=challenges,
        limitations=limitations,
    )
    fingerprint = transient_perspective_fingerprint(definition)
    definition = PerspectiveDefinition(
        id=f"transient:{fingerprint.removeprefix('sha256:')[:12]}",
        version=TRANSIENT_PERSPECTIVE_VERSION,
        label=label,
        purpose=purpose,
        questions=questions,
        challenges=challenges,
        limitations=limitations,
    )
    metadata = {
        "origin": TRANSIENT_PERSPECTIVE_ORIGIN,
        "definition_fingerprint": fingerprint,
        "definition": transient_perspective_semantics(definition),
    }
    return PerspectiveResolution(definition=definition, receipt_metadata=metadata)


def resolve_perspective_request(
    *,
    perspective_id: Any = None,
    perspective_draft: Any = None,
    saved_perspective_id: Any = None,
    saved_resolver: Any = None,
) -> PerspectiveResolution:
    has_id = bool(_clean_text(perspective_id))
    has_draft = isinstance(perspective_draft, dict)
    has_saved = bool(_clean_text(saved_perspective_id))
    if sum(1 for item in (has_id, has_draft, has_saved) if item) != 1:
        raise ValueError("Provide exactly one of perspective_id, perspective_draft, or saved_perspective_id.")
    if has_id:
        definition = perspective_definition(_clean_text(perspective_id))
        if definition is None:
            raise ValueError("unknown Perspective")
        return PerspectiveResolution(definition=definition)
    if has_saved:
        if saved_resolver is None:
            raise ValueError("saved Perspective resolver is unavailable")
        return saved_resolver(_clean_text(saved_perspective_id))
    return normalize_transient_perspective_draft(perspective_draft)


def normalize_reader_selection_scope(scope: dict[str, Any]) -> dict[str, object]:
    primary = scope.get("primary") if isinstance(scope.get("primary"), dict) else scope
    text = _clean_text(primary.get("text"))
    if not text:
        raise ValueError("Scope requires selected Reader text.")
    if _clean_text(primary.get("kind") or "reader_selection") != "reader_selection":
        raise ValueError("This Perspective Run supports only Reader selection Scope.")
    supporting_payload = scope.get("supporting") if isinstance(scope.get("supporting"), dict) else {}
    supported_keys = {"governing_question", "current_page"}
    for key, value in supporting_payload.items():
        if key not in supported_keys and isinstance(value, dict) and value.get("include"):
            raise ValueError(f"Unsupported Scope inclusion: {key}.")

    supporting: list[dict[str, object]] = []
    governing_payload = (
        supporting_payload.get("governing_question")
        if isinstance(supporting_payload.get("governing_question"), dict)
        else {}
    )
    include_governing = bool(governing_payload.get("include"))
    governing_text = _clean_text(governing_payload.get("text"))
    if include_governing:
        if not governing_text:
            raise ValueError("Included governing question is unavailable.")
        supporting.append({
            "kind": "governing_question",
            "text": governing_text,
            "included": True,
            "role": "supporting",
            "evidence_status": "investigation_context",
            "source_metadata_origin": "reader_client",
        })

    page_payload = (
        supporting_payload.get("current_page")
        if isinstance(supporting_payload.get("current_page"), dict)
        else {}
    )
    include_current_page = bool(page_payload.get("include"))
    page_text = _clean_text(page_payload.get("text"))
    if include_current_page:
        if not page_text:
            raise ValueError("Included current page source text is unavailable.")
        supporting.append({
            "kind": "current_page",
            "text": page_text,
            "included": True,
            "role": "supporting",
            "evidence_status": "source_context",
            "source_document_id": _clean_text(
                page_payload.get("source_document_id") or primary.get("source_document_id")
            ),
            "page": page_payload.get("page") or primary.get("page"),
            "source_locators": _clean_string_list(page_payload.get("source_locators")),
            "extraction_ids": _clean_string_list(page_payload.get("extraction_ids")),
            "source_metadata_origin": "reader_client",
        })

    receipt: dict[str, object] = {
        "primary": {
            "kind": "reader_selection",
            "text": text,
            "role": "primary",
            "evidence_status": "source_evidence",
            "source_document_id": _clean_text(primary.get("source_document_id")),
            "page": primary.get("page"),
            "locator": _clean_text(primary.get("locator")),
            "source_locators": _clean_string_list(primary.get("source_locators")),
            "extraction_ids": _clean_string_list(primary.get("extraction_ids")),
            "source_metadata_origin": "reader_client",
        },
        "supporting": supporting,
        "included": {
            "governing_question": include_governing,
            "current_page": include_current_page,
        },
        "excluded": {
            "governing_question": not include_governing,
            "current_page": not include_current_page,
            "entire_corpus": True,
            "all_notes": True,
            "accepted_interpretations": True,
            "other_documents": True,
        },
    }
    return receipt


def build_perspective_prompt(
    definition: PerspectiveDefinition,
    *,
    question: str,
    scope_receipt: dict[str, object],
    prior_proposed_readings: list[dict[str, object]] | None = None,
) -> str:
    primary = scope_receipt["primary"]
    selected_text = str(primary["text"])
    supporting = [
        item for item in scope_receipt.get("supporting", [])
        if isinstance(item, dict) and item.get("included")
    ]
    lines = [
        "You are performing a Hermeneia Perspective Run.",
        "",
        "This is a proposed interpretive reading, not a canonical Interpretation.",
        "Remain within the supplied evidence boundary.",
        "Distinguish what the evidence supports from what you infer.",
        "Surface uncertainty and alternatives.",
        "Do not alter, correct, or normalize the source text.",
        "Do not silently broaden context beyond the Scope Receipt.",
        "",
        f"Perspective: {definition.label}",
        f"Perspective ID: {definition.id}",
        f"Purpose: {definition.purpose}",
        "",
        "This Perspective tends to ask:",
        *[f"- {item}" for item in definition.questions],
        "",
        "This Perspective should challenge:",
        *[f"- {item}" for item in definition.challenges],
        "",
        "Known limitations:",
        *[f"- {item}" for item in definition.limitations],
        "",
        f"Question: {question.strip()}",
        "",
        "Scope Receipt:",
        f"- Primary kind: {primary.get('kind')}",
        f"- Source document: {primary.get('source_document_id') or 'unknown'}",
        f"- Page: {primary.get('page') or 'unknown'}",
        f"- Locator: {primary.get('locator') or 'unknown'}",
        f"- Supporting items: {len(supporting)}",
        "",
        "PRIMARY SOURCE ATTENTION:",
        "The following selected Reader passage is the center of the Question.",
        selected_text,
    ]
    if definition.version:
        lines.insert(11, f"Perspective version: {definition.version}")
    current_pages = [item for item in supporting if item.get("kind") == "current_page"]
    if current_pages:
        lines.extend([
            "",
            "SUPPORTING SOURCE CONTEXT:",
            "This source material was explicitly included for context. The primary passage remains the center of the Question.",
        ])
        for item in current_pages:
            lines.extend([
                "",
                f"Current page {item.get('page') or 'unknown'}:",
                str(item.get("text") or ""),
            ])
    governing_questions = [
        item for item in supporting if item.get("kind") == "governing_question"
    ]
    if governing_questions:
        lines.extend([
            "",
            "SUPPORTING INVESTIGATION CONTEXT:",
            "This is investigation context, not source evidence, and it does not replace the User Question.",
        ])
        for item in governing_questions:
            lines.extend(["", "Governing Question:", str(item.get("text") or "")])
    prior_readings = prior_proposed_readings or []
    if prior_readings:
        lines.extend([
            "",
            "PRIOR PROPOSED READINGS — DELIBERATION CONTEXT, NOT SOURCE EVIDENCE",
            "These are non-canonical model-generated deliberation material.",
            "They are not source evidence and may be wrong.",
            "You may build on, challenge, distinguish, or reject prior proposed readings.",
            "Do not treat them as evidence merely because another Perspective produced them.",
            "Ground claims in the supplied source Scope.",
        ])
        for item in prior_readings:
            perspective = item.get("perspective") if isinstance(item.get("perspective"), dict) else {}
            label = str(perspective.get("label") or perspective.get("id") or "Prior Perspective")
            version = str(perspective.get("version") or "")
            perspective_id = str(perspective.get("perspective_id") or perspective.get("id") or "")
            response = str(item.get("response") or "")
            identity = f"{label} v{version}".rstrip() if version else label
            if perspective_id:
                identity = f"{identity} ({perspective_id})"
            lines.extend(["", f"{identity}:", response])
    lines.extend([
        "",
        "Return a concise proposed reading that answers the Question through the selected Perspective.",
        "Do not claim the response has entered the interpretation record.",
    ])
    return "\n".join(lines)


def build_perspective_receipt(
    definition: PerspectiveDefinition,
    *,
    question: str,
    scope_receipt: dict[str, object],
    execution: dict[str, object],
    response: str,
    perspective_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    perspective = {
        "id": definition.id,
        "label": definition.label,
    }
    if definition.version:
        perspective["version"] = definition.version
    if perspective_metadata:
        perspective.update(perspective_metadata)
    return {
        "operation": "perspective_run",
        "perspective": perspective,
        "question": question.strip(),
        "scope_receipt": scope_receipt,
        "execution": execution,
        "response": response,
        "status": "succeeded",
        "canonical_status": "not_persisted",
    }


def room_perspective_definitions(
    perspective_ids: tuple[str, ...] = DEFAULT_ROOM_PERSPECTIVES,
) -> list[PerspectiveDefinition]:
    definitions: list[PerspectiveDefinition] = []
    for perspective_id in perspective_ids:
        definition = perspective_definition(perspective_id)
        if definition is None:
            raise ValueError(f"unknown room Perspective: {perspective_id}")
        definitions.append(definition)
    return definitions


def _room_perspective_payload(
    definition: PerspectiveDefinition,
    metadata: dict[str, object] | None,
) -> dict[str, object]:
    perspective: dict[str, object] = {
        "id": definition.id,
        "label": definition.label,
    }
    if definition.version:
        perspective["version"] = definition.version
    if metadata:
        perspective.update(metadata)
    return perspective


def room_participant_perspective_payload(
    participant: RoomParticipantResolution,
) -> dict[str, object]:
    return _room_perspective_payload(participant.definition, participant.receipt_metadata)


def resolve_room_participants(
    participants: Any = None,
    *,
    saved_resolver: Any = None,
) -> tuple[str, list[RoomParticipantResolution]]:
    if participants is None:
        return "default", [
            RoomParticipantResolution(
                ordinal=order,
                participant_kind="built_in",
                definition=definition,
                receipt_metadata={"origin": "built_in"},
            )
            for order, definition in enumerate(room_perspective_definitions(), start=1)
        ]
    if not isinstance(participants, list):
        raise ValueError("participants must be a list when supplied")
    if len(participants) < 2:
        raise ValueError("Ask the Room requires at least 2 participants")
    if len(participants) > 4:
        raise ValueError("Ask the Room supports at most 4 participants")

    allowed_fields = {"kind", "perspective_id"}
    seen_ids: set[str] = set()
    resolved: list[RoomParticipantResolution] = []
    for index, item in enumerate(participants, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"participant {index} must be an object")
        unsupported = [
            key for key, value in item.items()
            if key not in allowed_fields and value not in (None, "", [], {})
        ]
        if unsupported:
            raise ValueError(f"unsupported participant field: {unsupported[0]}")
        kind = _clean_text(item.get("kind"))
        perspective_id = _clean_text(item.get("perspective_id"))
        if not kind:
            raise ValueError(f"participant {index} kind is required")
        if not perspective_id:
            raise ValueError(f"participant {index} perspective_id is required")
        if perspective_id in seen_ids:
            raise ValueError("duplicate Room participant Perspective ID")
        seen_ids.add(perspective_id)

        if kind == "built_in":
            definition = perspective_definition(perspective_id)
            if definition is None:
                raise ValueError("unknown built-in Perspective")
            resolved.append(RoomParticipantResolution(
                ordinal=index,
                participant_kind=kind,
                definition=definition,
                receipt_metadata={"origin": "built_in"},
            ))
            continue

        if kind == "saved":
            if perspective_id.startswith("transient:"):
                raise ValueError("transient Perspective drafts cannot be Room participants")
            if saved_resolver is None:
                raise ValueError("saved Perspective resolver is unavailable")
            saved = saved_resolver(perspective_id)
            metadata = dict(saved.receipt_metadata or {})
            if metadata.get("identity_scheme") != "perspective-frame-v2":
                raise ValueError("saved Room participants must be frame-v2 Perspectives")
            resolved.append(RoomParticipantResolution(
                ordinal=index,
                participant_kind=kind,
                definition=saved.definition,
                receipt_metadata=metadata,
            ))
            continue

        raise ValueError(f"unknown participant kind: {kind}")

    return "user_selected", resolved


def room_definitions_payload() -> list[dict[str, object]]:
    return [
        {"order": order, **definition.to_dict()}
        for order, definition in enumerate(room_perspective_definitions(), start=1)
    ]


def build_perspective_room_receipt(
    *,
    question: str,
    scope_receipt: dict[str, object],
    model: dict[str, object],
    participants: list[dict[str, object]],
    status: str,
    roster_source: str = "default",
) -> dict[str, object]:
    return {
        "operation": "perspective_room",
        "roster_source": roster_source,
        "participant_count": len(participants),
        "question": question.strip(),
        "scope_receipt": scope_receipt,
        "model": model,
        "participants": participants,
        "status": status,
        "canonical_status": "not_persisted",
    }
