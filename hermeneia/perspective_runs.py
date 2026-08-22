"""Transient Perspective Run primitives.

A Perspective Run is inquiry-time assistance. It binds a frame, an explicit
scope receipt, a human question, and an execution identity, then returns a
proposed reading. It does not create a canonical Interpretation.
"""
from __future__ import annotations

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


def perspective_definition(perspective_id: str) -> PerspectiveDefinition | None:
    for definition in PERSPECTIVE_DEFINITIONS:
        if definition.id == perspective_id:
            return definition
    return None


def perspective_definitions_payload() -> list[dict[str, object]]:
    return [definition.to_dict() for definition in PERSPECTIVE_DEFINITIONS]


def normalize_reader_selection_scope(scope: dict[str, Any]) -> dict[str, object]:
    primary = scope.get("primary") if isinstance(scope.get("primary"), dict) else scope
    text = str(primary.get("text") or "").strip()
    if not text:
        raise ValueError("Scope requires selected Reader text.")
    if str(primary.get("kind") or "reader_selection") != "reader_selection":
        raise ValueError("This Perspective Run supports only Reader selection Scope.")
    receipt: dict[str, object] = {
        "primary": {
            "kind": "reader_selection",
            "text": text,
            "source_document_id": str(primary.get("source_document_id") or ""),
            "page": primary.get("page"),
            "locator": str(primary.get("locator") or ""),
            "source_locators": [
                str(value)
                for value in primary.get("source_locators") or []
                if str(value).strip()
            ],
            "extraction_ids": [
                str(value)
                for value in primary.get("extraction_ids") or []
                if str(value).strip()
            ],
            "source_metadata_origin": "reader_client",
        },
        "included": {
            "governing_question": False,
        },
        "excluded": {
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
        f"Perspective version: {definition.version}",
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
    ]
    prior_readings = prior_proposed_readings or []
    if prior_readings:
        lines.extend([
            "",
            "Prior Proposed Readings (Deliberation Context):",
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
            response = str(item.get("response") or "")
            lines.extend(["", f"{label} v{version}:".rstrip(), response])
    lines.extend([
        "",
        "Scope Receipt:",
        f"- Primary kind: {primary.get('kind')}",
        f"- Source document: {primary.get('source_document_id') or 'unknown'}",
        f"- Page: {primary.get('page') or 'unknown'}",
        f"- Locator: {primary.get('locator') or 'unknown'}",
        "",
        "Selected Reader passage:",
        selected_text,
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
) -> dict[str, object]:
    return {
        "operation": "perspective_run",
        "perspective": {
            "id": definition.id,
            "version": definition.version,
            "label": definition.label,
        },
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
) -> dict[str, object]:
    return {
        "operation": "perspective_room",
        "question": question.strip(),
        "scope_receipt": scope_receipt,
        "model": model,
        "participants": participants,
        "status": status,
        "canonical_status": "not_persisted",
    }
