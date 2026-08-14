"""Deterministic, provider-free synthesis packets over compiled study records."""
from __future__ import annotations

import json
from typing import Any

from hermeneia.reader_span import (
    reader_span_display_locator,
    reader_span_raw_locator,
)

from .compiler import RANK_LABELS, classify_mark, compile_study


PACKET_VERSION = "study-synthesis-packet-v1"


def _text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _rank(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and 1 <= value <= 5:
        return value
    if isinstance(value, str) and value.strip().isdecimal():
        parsed = int(value.strip())
        return parsed if 1 <= parsed <= 5 else 0
    return 0


def _tags(value: object) -> list[str]:
    if isinstance(value, list):
        return [tag for tag in value if isinstance(tag, str)]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return []
        if isinstance(parsed, list):
            return [tag for tag in parsed if isinstance(tag, str)]
    return []


def _record_key(record: dict[str, Any]) -> tuple[str, str]:
    return (
        str(record.get("created_at") or ""),
        str(record.get("id") or ""),
    )


def _source_locator_fields(source_locator: object) -> dict[str, str | None]:
    display = reader_span_display_locator(source_locator)
    raw_span = reader_span_raw_locator(source_locator)
    fields = {"source_locator": display}
    if raw_span:
        fields["reader_span_locator"] = raw_span
    return fields


def _active_annotations(
    annotations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        annotation
        for annotation in annotations
        if annotation.get("status") != "dismissed"
    ]


def _ranked_highlights(
    annotations: list[dict[str, Any]],
    document_names: dict[str, str],
) -> list[dict[str, Any]]:
    ranked = [
        annotation
        for annotation in annotations
        if _rank(annotation.get("rank"))
    ]
    ranked.sort(
        key=lambda annotation: (
            -_rank(annotation.get("rank")),
            str(annotation.get("created_at") or ""),
            str(annotation.get("id") or ""),
        )
    )
    return [
        {
            "id": annotation.get("id"),
            "mark_type": classify_mark(annotation),
            "rank": _rank(annotation.get("rank")),
            "rank_label": RANK_LABELS[_rank(annotation.get("rank"))],
            "selected_text": _text(annotation.get("selected_text")),
            "note_text": _text(annotation.get("note_text")),
            "question_text": _text(annotation.get("question_text")),
            "theme_bucket": _text(annotation.get("theme_bucket")),
            "evidence_bucket": _text(annotation.get("evidence_bucket")),
            "relevance": _text(annotation.get("relevance")),
            "status": annotation.get("status"),
            "tags": _tags(annotation.get("tags")),
            "source": {
                "document_id": annotation.get("source_document_id"),
                "filename": document_names.get(
                    str(annotation.get("source_document_id") or "")
                ),
                "source_role": annotation.get("source_role") or "primary",
                "page": annotation.get("page"),
                **_source_locator_fields(annotation.get("source_locator")),
                "observation_id": annotation.get("observation_id"),
            },
            "created_at": annotation.get("created_at"),
        }
        for annotation in ranked
    ]


def _theme_buckets(
    annotations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for annotation in annotations:
        name = _text(annotation.get("theme_bucket"))
        if name:
            buckets.setdefault(name, []).append(annotation)
    return [
        {
            "name": name,
            "count": len(items),
            "ranked_count": sum(1 for item in items if _rank(item.get("rank"))),
            "highlight_ids": sorted(
                str(item.get("id")) for item in items if item.get("id")
            ),
        }
        for name, items in sorted(
            buckets.items(),
            key=lambda item: (
                -sum(_rank(annotation.get("rank")) for annotation in item[1]),
                -len(item[1]),
                item[0],
            ),
        )
    ]


def _field_note_reference(note: dict[str, Any], field: str) -> dict[str, Any]:
    return {
        "field_note_id": note.get("id"),
        "text": _text(note.get(field)),
        "source": {
            "document_id": note.get("source_document_id"),
            "filename": note.get("original_filename"),
            "page": note.get("page"),
        },
        "governing_question": _text(note.get("governing_question")),
        "created_at": note.get("created_at"),
    }


def _field_note_packet(
    field_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    corpus_notes = [
        note for note in field_notes
        if (note.get("lane") or "corpus") == "corpus"
    ]
    latest_first = sorted(corpus_notes, key=_record_key, reverse=True)
    current = next(
        (
            _field_note_reference(note, "understanding")
            for note in latest_first
            if _text(note.get("understanding"))
        ),
        None,
    )
    pressing = [
        _field_note_reference(note, "pressing_questions")
        for note in latest_first
        if _text(note.get("pressing_questions"))
    ]
    return {
        "current_understanding": current,
        "pressing_questions": pressing,
    }


def _governing_question(
    explicit_question: str | None,
    field_notes: list[dict[str, Any]],
) -> str | None:
    if _text(explicit_question):
        return _text(explicit_question)
    latest_first = sorted(field_notes, key=_record_key, reverse=True)
    return next(
        (
            question
            for note in latest_first
            if (question := _text(note.get("governing_question")))
        ),
        None,
    )


def _unresolved_questions(
    annotations: list[dict[str, Any]],
    field_note_packet: dict[str, Any],
    document_names: dict[str, str],
) -> list[dict[str, Any]]:
    highlight_questions = [
        {
            "text": _text(annotation.get("question_text")),
            "record_type": "reader_highlight",
            "record_id": annotation.get("id"),
            "rank": _rank(annotation.get("rank")) or None,
            "source": {
                "document_id": annotation.get("source_document_id"),
                "filename": document_names.get(
                    str(annotation.get("source_document_id") or "")
                ),
                "page": annotation.get("page"),
                **_source_locator_fields(annotation.get("source_locator")),
            },
            "created_at": annotation.get("created_at"),
        }
        for annotation in annotations
        if _text(annotation.get("question_text"))
    ]
    field_note_questions = [
        {
            "text": question["text"],
            "record_type": "field_note",
            "record_id": question["field_note_id"],
            "rank": None,
            "source": question["source"],
            "created_at": question["created_at"],
        }
        for question in field_note_packet["pressing_questions"]
    ]
    return sorted(
        highlight_questions + field_note_questions,
        key=lambda question: (
            str(question.get("created_at") or ""),
            str(question.get("record_type") or ""),
            str(question.get("record_id") or ""),
        ),
    )


def _reading_trail(
    documents: list[dict[str, Any]],
    reading_progress: list[dict[str, Any]],
) -> dict[str, Any]:
    progress_by_document = {
        str(progress.get("document_id") or ""): progress
        for progress in reading_progress
    }
    rows = []
    for document in documents:
        document_id = str(document.get("id") or "")
        progress = progress_by_document.get(document_id, {})
        total_pages = int(document.get("total_pages") or 0)
        raw_pages = progress.get("pages_read")
        if isinstance(raw_pages, str):
            try:
                raw_pages = json.loads(raw_pages)
            except (TypeError, ValueError):
                raw_pages = []
        pages_read = sorted(
            {
                int(page)
                for page in (raw_pages if isinstance(raw_pages, list) else [])
                if isinstance(page, (int, float))
                and int(page) > 0
                and (not total_pages or int(page) <= total_pages)
            }
        )
        rows.append({
            "document_id": document_id,
            "filename": document.get("filename"),
            "pages_read": pages_read,
            "pages_read_count": len(pages_read),
            "total_pages": total_pages,
            "percent_read": (
                round(len(pages_read) / total_pages * 100, 1)
                if total_pages else 0.0
            ),
            "last_page": progress.get("last_page"),
            "completed_at": progress.get("completed_at"),
            "updated_at": progress.get("updated_at"),
        })
    return {
        "documents": rows,
        "total_pages_read": sum(row["pages_read_count"] for row in rows),
    }


def _lineage(
    active: list[dict[str, Any]],
    field_note_packet: dict[str, Any],
    document_names: dict[str, str],
    thesis_ids: list[Any],
    strongest_ids: list[Any],
    evidence_ids: list[Any],
) -> dict[str, Any]:
    """Deterministic backward references from packet items to their records.

    For every study record that surfaces anywhere in the packet, record the
    roles it plays (ranked highlight, theme bucket, thesis candidate, …) and
    the single source chain that grounds it. Absent source fields are listed
    explicitly in ``missing`` rather than silently dropped, so an untraceable
    claim is visible as such. This reads only the records already passed in;
    it performs no provider call and touches no canonical evidence.
    """
    thesis = {str(i) for i in thesis_ids}
    strongest = {str(i) for i in strongest_ids}
    evidence = {str(i) for i in evidence_ids}
    records: list[dict[str, Any]] = []

    for annotation in sorted(active, key=_record_key):
        highlight_id = annotation.get("id")
        if not highlight_id:
            continue
        roles: list[str] = []
        if _rank(annotation.get("rank")):
            roles.append("ranked_highlight")
        theme = _text(annotation.get("theme_bucket"))
        if theme:
            roles.append(f"theme_bucket:{theme}")
        if _text(annotation.get("question_text")):
            roles.append("unresolved_question")
        if str(highlight_id) in thesis:
            roles.append("thesis_candidate")
        if str(highlight_id) in strongest:
            roles.append("strongest_observation")
        if str(highlight_id) in evidence:
            roles.append("evidence_bucket")
        if not roles:
            continue  # highlight is not surfaced anywhere in the packet
        document_id = annotation.get("source_document_id")
        source = {
            "document_id": document_id,
            "filename": document_names.get(str(document_id or "")),
            "page": annotation.get("page"),
            **_source_locator_fields(annotation.get("source_locator")),
            "observation_id": annotation.get("observation_id"),
        }
        missing = [
            field for field in ("page", "source_locator")
            if source.get(field) in (None, "")
        ]
        traceable = bool(document_id) and not (
            {"page", "source_locator"} <= set(missing)
        )
        records.append({
            "record_type": "reader_highlight",
            "record_id": highlight_id,
            "roles": roles,
            "source": source,
            "traceable": traceable,
            "missing": missing,
        })

    field_note_roles: dict[Any, dict[str, Any]] = {}
    understanding = field_note_packet.get("current_understanding")
    if understanding:
        field_note_roles.setdefault(
            understanding.get("field_note_id"),
            {"roles": [], "source": understanding.get("source", {})},
        )["roles"].append("field_note_understanding")
    for question in field_note_packet.get("pressing_questions", []):
        entry = field_note_roles.setdefault(
            question.get("field_note_id"),
            {"roles": [], "source": question.get("source", {})},
        )
        entry["roles"].append("field_note_question")

    for field_note_id, entry in sorted(
        field_note_roles.items(), key=lambda item: str(item[0] or "")
    ):
        if not field_note_id:
            continue
        src = entry["source"] or {}
        source = {
            "document_id": src.get("document_id"),
            "filename": src.get("filename"),
            "page": src.get("page"),
            "source_locator": None,
        }
        traceable = bool(source["document_id"]) and source["page"] is not None
        records.append({
            "record_type": "field_note",
            "record_id": field_note_id,
            "roles": entry["roles"],
            "source": source,
            "traceable": traceable,
            "missing": ["source_locator"],
            "missing_reason": (
                "Field notes are recorded at page granularity; no block-level "
                "locator exists."
            ),
        })

    return {
        "note": (
            "Deterministic backward references from packet items to the study "
            "records and source locations that produced them. No canonical "
            "evidence is read or modified."
        ),
        "records": records,
        "counts": {
            "records": len(records),
            "traceable": sum(1 for record in records if record["traceable"]),
            "untraceable": sum(1 for record in records if not record["traceable"]),
        },
    }


def compile_synthesis_packet(
    annotations: list[dict[str, Any]],
    *,
    documents: list[dict[str, Any]],
    field_notes: list[dict[str, Any]],
    reading_progress: list[dict[str, Any]],
    compiled_at: str,
    scope_document_id: str | None = None,
    governing_question: str | None = None,
    working_thesis: str | None = None,
) -> dict[str, Any]:
    """Compile current study records into compact, inspectable prompt material.

    This function performs no provider calls and creates no canonical object.
    ``compiled_at`` is explicit so identical inputs produce identical output.
    """
    active = _active_annotations(annotations)
    ordered_documents = sorted(
        documents,
        key=lambda document: (
            str(document.get("filename") or ""),
            str(document.get("id") or ""),
        ),
    )
    document_names = {
        str(document.get("id") or ""): str(document.get("filename") or "")
        for document in ordered_documents
    }
    compiled_record = compile_study(active)
    field_note_packet = _field_note_packet(field_notes)
    ranked_highlights = _ranked_highlights(active, document_names)

    thesis_candidate_ids = [
        item.get("id")
        for item in compiled_record["thesis_candidates"]
        if item.get("id")
    ]
    strongest_observation_ids = [
        item.get("id")
        for item in compiled_record["strongest_observations"]
        if item.get("id")
    ]
    evidence_bucket_ids = [
        item.get("id")
        for item in compiled_record["evidence_bucket"]
        if item.get("id")
    ]

    return {
        "packet_type": PACKET_VERSION,
        "compiled_at": compiled_at,
        "identity": {
            "scope": "document" if scope_document_id else "study",
            "document_id": scope_document_id,
            "documents": [
                {
                    "id": document.get("id"),
                    "filename": document.get("filename"),
                    "file_hash": document.get("file_hash"),
                    "source_role": document.get("source_role") or "primary",
                    "total_pages": document.get("total_pages"),
                    "excluded": bool(document.get("excluded_from_analysis")),
                }
                for document in ordered_documents
            ],
        },
        "governing_question": _governing_question(
            governing_question,
            field_notes,
        ),
        "working_thesis": _text(working_thesis),
        "ranked_highlights": ranked_highlights,
        "theme_buckets": _theme_buckets(active),
        "field_notes": field_note_packet,
        "unresolved_questions": _unresolved_questions(
            active,
            field_note_packet,
            document_names,
        ),
        "adopted_companion_notes": {
            "identification_available": False,
            "items": [],
            "note": (
                "Saved Companion text is included as Field Notes, but the current "
                "Field Notes schema does not preserve its draft origin."
            ),
        },
        "reading_trail": _reading_trail(
            ordered_documents,
            reading_progress,
        ),
        "compiled_record": {
            "counts": compiled_record["counts"],
            "thesis_candidate_ids": thesis_candidate_ids,
            "strongest_observation_ids": strongest_observation_ids,
            "evidence_bucket_ids": evidence_bucket_ids,
            "suggested_next_steps": compiled_record["suggested_next_steps"],
        },
        "lineage": _lineage(
            active,
            field_note_packet,
            document_names,
            thesis_candidate_ids,
            strongest_observation_ids,
            evidence_bucket_ids,
        ),
        "provenance": {
            "compiler": "hermeneia.study.compile_synthesis_packet",
            "version": PACKET_VERSION,
            "compiled_at": compiled_at,
            "provider_free": True,
            "canonical_evidence_modified": False,
            "source_records": {
                "source_document_ids": [
                    document.get("id") for document in ordered_documents
                ],
                "reader_highlight_ids": [
                    annotation.get("id")
                    for annotation in sorted(active, key=_record_key)
                ],
                "field_note_ids": [
                    note.get("id")
                    for note in sorted(field_notes, key=_record_key)
                ],
                "reading_progress_document_ids": sorted(
                    str(progress.get("document_id"))
                    for progress in reading_progress
                    if progress.get("document_id")
                ),
            },
        },
    }
