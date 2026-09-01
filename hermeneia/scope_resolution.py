"""Transient Scope resolution for provider-backed operations.

This module deliberately does not create a canonical Scope object. It resolves
browser Working Scope claims against the active workspace database and returns
an inspectable receipt for the exact material allowed to cross a provider
boundary.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

from .reader_span import decode_reader_span_locator
from .study import compile_synthesis_packet
from .web.reader_projection import project_reader_page


class ScopeResolutionError(ValueError):
    """Raised when Working Scope cannot be resolved safely."""


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _clean_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _active_document(conn: sqlite3.Connection, doc_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM source_documents WHERE id = ?",
        (doc_id,),
    ).fetchone()
    if row is None:
        raise ScopeResolutionError("document not found")
    if int(row["excluded_from_analysis"] or 0):
        raise ScopeResolutionError("document is excluded_from_analysis")
    return row


def _document_payload(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "filename": row["original_filename"],
        "file_hash": row["file_hash"],
        "source_role": row["source_role"] or "primary",
        "total_pages": row["total_pages"],
        "excluded_from_analysis": bool(row["excluded_from_analysis"]),
    }


def _page_extractions(
    conn: sqlite3.Connection,
    *,
    doc_id: str,
    page: int,
) -> list[dict[str, object]]:
    rows = conn.execute(
        """SELECT id, page, region, raw_text, source_locator
           FROM source_extractions
           WHERE document_id = ? AND page = ?
           ORDER BY page,
                    CASE
                      WHEN region GLOB 'block:[0-9]*'
                      THEN CAST(substr(region, 7) AS INTEGER)
                      ELSE 2147483647
                    END,
                    source_locator""",
        (doc_id, page),
    ).fetchall()
    return [dict(row) for row in rows]


def _projected_page(
    conn: sqlite3.Connection,
    *,
    doc_id: str,
    page: int,
) -> list[dict[str, object]]:
    blocks = project_reader_page(_page_extractions(conn, doc_id=doc_id, page=page))["extractions"]
    result = [dict(block) for block in blocks]
    if not result:
        raise ScopeResolutionError("requested Reader page has no source text")
    return result


def _block_ids(block: dict[str, object]) -> list[str]:
    projection = block.get("reader_projection")
    projection = projection if isinstance(projection, dict) else {}
    canonical = block.get("canonical_extractions")
    ids = _clean_string_list(projection.get("source_extraction_ids"))
    if isinstance(canonical, list):
        ids.extend(
            _clean_text(item.get("id"))
            for item in canonical
            if isinstance(item, dict) and _clean_text(item.get("id"))
        )
    ids.append(_clean_text(block.get("source_extraction_id")))
    return _unique(ids)


def _block_locators(block: dict[str, object]) -> list[str]:
    projection = block.get("reader_projection")
    projection = projection if isinstance(projection, dict) else {}
    canonical = block.get("canonical_extractions")
    locators = _clean_string_list(projection.get("source_locators"))
    if isinstance(canonical, list):
        locators.extend(
            _clean_text(item.get("source_locator"))
            for item in canonical
            if isinstance(item, dict) and _clean_text(item.get("source_locator"))
        )
    locators.append(_clean_text(block.get("source_locator")))
    return _unique(locators)


def _block_context(
    block: dict[str, object],
    *,
    block_index: int,
    page: int,
) -> dict[str, object]:
    projection = block.get("reader_projection")
    projection = projection if isinstance(projection, dict) else {}
    display_spans = projection.get("display_source_spans")
    return {
        "block_index": block_index,
        "page": page,
        "source_locator": _clean_text(block.get("source_locator")),
        "source_locators": _block_locators(block),
        "extraction_ids": _block_ids(block),
        "display_source_spans": display_spans if isinstance(display_spans, list) else [],
    }


def _has_provenance(value: dict[str, object]) -> bool:
    return bool(_clean_string_list(value.get("source_locators")) or _clean_string_list(value.get("extraction_ids")))


def _provenance_intersects(
    left: dict[str, object],
    right: dict[str, object],
) -> bool:
    left_locators = set(_clean_string_list(left.get("source_locators")))
    right_locators = set(_clean_string_list(right.get("source_locators")))
    left_ids = set(_clean_string_list(left.get("extraction_ids")))
    right_ids = set(_clean_string_list(right.get("extraction_ids")))
    return bool((left_locators and right_locators and left_locators & right_locators) or (left_ids and right_ids and left_ids & right_ids))


def _span_point(point: object) -> dict[str, object]:
    if not isinstance(point, dict):
        return {}
    return {
        "block_index": point.get("block_index"),
        "offset": point.get("offset"),
        "source_locator": _clean_text(point.get("source_locator")),
        "source_locators": _unique(_clean_string_list(point.get("source_locators")) + [_clean_text(point.get("source_locator"))]),
        "extraction_ids": _unique(_clean_string_list(point.get("extraction_ids")) + [_clean_text(point.get("extraction_id"))]),
    }


def _point_block_index(point: dict[str, object]) -> int | None:
    try:
        value = int(point.get("block_index"))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _point_offset(point: dict[str, object], text: str) -> int:
    try:
        value = int(point.get("offset"))
    except (TypeError, ValueError):
        raise ScopeResolutionError("Reader selection locator is missing offsets")
    if value < 0 or value > len(text):
        raise ScopeResolutionError("Reader selection locator offset is outside the source block")
    return value


def _matching_point_index(
    contexts: list[dict[str, object]],
    point: dict[str, object],
) -> int:
    if not _has_provenance(point):
        raise ScopeResolutionError("Reader selection locator lacks usable source provenance")
    hinted = _point_block_index(point)
    if hinted is not None and hinted < len(contexts):
        hinted_context = contexts[hinted]
        if _provenance_intersects(hinted_context, point):
            return hinted
    matches = [
        index
        for index, context in enumerate(contexts)
        if _provenance_intersects(context, point)
    ]
    if len(matches) != 1:
        raise ScopeResolutionError("Reader selection locator cannot be mapped safely")
    return matches[0]


def _resolved_reader_selection_text(
    blocks: list[dict[str, object]],
    contexts: list[dict[str, object]],
    locator: str,
) -> tuple[str, dict[str, object]]:
    span = decode_reader_span_locator(locator)
    if span is None:
        raise ScopeResolutionError("Reader selection requires a valid reader-span locator")
    if span.get("coordinate_space") != "reader_projection":
        raise ScopeResolutionError("Reader selection locator has unsupported coordinate space")
    if not _has_provenance({
        "source_locators": span.get("source_locators"),
        "extraction_ids": span.get("extraction_ids"),
    }):
        raise ScopeResolutionError("Reader selection locator lacks usable source provenance")
    start_point = _span_point(span.get("start"))
    end_point = _span_point(span.get("end"))
    start_index = _matching_point_index(contexts, start_point)
    end_index = _matching_point_index(contexts, end_point)
    if end_index < start_index:
        raise ScopeResolutionError("Reader selection locator has invalid block order")

    parts: list[str] = []
    block_ranges: list[dict[str, object]] = []
    for index in range(start_index, end_index + 1):
        block_text = str(blocks[index].get("text") or "")
        start = _point_offset(start_point, block_text) if index == start_index else 0
        end = _point_offset(end_point, block_text) if index == end_index else len(block_text)
        if end < start:
            raise ScopeResolutionError("Reader selection locator has invalid offsets")
        selected = block_text[start:end]
        if selected:
            parts.append(selected)
        block_ranges.append({
            "block_index": index,
            "start": start,
            "end": end,
            "source_locators": contexts[index]["source_locators"],
            "extraction_ids": contexts[index]["extraction_ids"],
        })
    text = "\n\n".join(parts).strip()
    if not text:
        raise ScopeResolutionError("Reader selection resolved to empty source text")
    return text, {"reader_span": span, "block_ranges": block_ranges}


def _verify_client_text(kind: str, client_text: object, resolved_text: str) -> None:
    supplied = _clean_text(client_text)
    if supplied and supplied != _clean_text(resolved_text):
        raise ScopeResolutionError(f"{kind} text disagrees with authoritative Reader source")


def _resolve_reader_selection(
    conn: sqlite3.Connection,
    primary: dict[str, Any],
) -> tuple[dict[str, object], dict[str, object]]:
    if _clean_text(primary.get("kind") or "reader_selection") != "reader_selection":
        raise ScopeResolutionError("This Perspective Run supports only Reader selection Scope.")
    doc_id = _clean_text(primary.get("source_document_id"))
    if not doc_id:
        raise ScopeResolutionError("Reader selection Scope requires source_document_id")
    try:
        page = int(primary.get("page"))
    except (TypeError, ValueError):
        raise ScopeResolutionError("Reader selection Scope requires page")
    doc = _active_document(conn, doc_id)
    blocks = _projected_page(conn, doc_id=doc_id, page=page)
    contexts = [
        _block_context(block, block_index=index, page=page)
        for index, block in enumerate(blocks)
    ]
    locator = _clean_text(primary.get("locator"))
    resolved_text, reconstruction = _resolved_reader_selection_text(blocks, contexts, locator)
    _verify_client_text("Reader selection", primary.get("text"), resolved_text)
    source_locators = _unique(
        locator
        for item in reconstruction["block_ranges"]
        for locator in _clean_string_list(item.get("source_locators"))
    )
    extraction_ids = _unique(
        extraction_id
        for item in reconstruction["block_ranges"]
        for extraction_id in _clean_string_list(item.get("extraction_ids"))
    )
    receipt = {
        "kind": "reader_selection",
        "text": resolved_text,
        "role": "primary",
        "evidence_status": "source_evidence",
        "source_document_id": doc_id,
        "source_document_filename": doc["original_filename"],
        "source_document_hash": doc["file_hash"],
        "page": page,
        "locator": locator,
        "source_locators": source_locators,
        "extraction_ids": extraction_ids,
        "source_metadata_origin": "server_resolved_reader_projection",
        "resolution": reconstruction,
    }
    material = {
        "kind": "reader_selection",
        "role": "primary",
        "text": resolved_text,
        "source_document_id": doc_id,
        "page": page,
        "locator": locator,
        "source_locators": source_locators,
        "extraction_ids": extraction_ids,
    }
    return receipt, material


def _resolve_current_page(
    conn: sqlite3.Connection,
    page_payload: dict[str, Any],
    *,
    fallback_doc_id: str,
    fallback_page: int,
) -> tuple[dict[str, object], dict[str, object]]:
    doc_id = _clean_text(page_payload.get("source_document_id")) or fallback_doc_id
    page = page_payload.get("page") or fallback_page
    try:
        page_number = int(page)
    except (TypeError, ValueError):
        raise ScopeResolutionError("Included current page requires page")
    doc = _active_document(conn, doc_id)
    blocks = _projected_page(conn, doc_id=doc_id, page=page_number)
    contexts = [
        _block_context(block, block_index=index, page=page_number)
        for index, block in enumerate(blocks)
    ]
    text = "\n\n".join(
        str(block.get("text") or "").strip()
        for block in blocks
        if str(block.get("text") or "").strip()
    ).strip()
    if not text:
        raise ScopeResolutionError("Included current page source text is unavailable")
    _verify_client_text("current page", page_payload.get("text"), text)
    source_locators = _unique(
        locator
        for context in contexts
        for locator in _clean_string_list(context.get("source_locators"))
    )
    extraction_ids = _unique(
        extraction_id
        for context in contexts
        for extraction_id in _clean_string_list(context.get("extraction_ids"))
    )
    receipt = {
        "kind": "current_page",
        "text": text,
        "included": True,
        "role": "supporting",
        "evidence_status": "source_context",
        "source_document_id": doc_id,
        "source_document_filename": doc["original_filename"],
        "source_document_hash": doc["file_hash"],
        "page": page_number,
        "source_locators": source_locators,
        "extraction_ids": extraction_ids,
        "source_metadata_origin": "server_resolved_reader_projection",
    }
    return receipt, dict(receipt)


def _load_highlights(
    conn: sqlite3.Connection,
    ids: list[str],
) -> list[dict[str, object]]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""SELECT *
            FROM reader_highlights
            WHERE id IN ({placeholders}) AND status != 'dismissed'""",
        ids,
    ).fetchall()
    by_id = {row["id"]: dict(row) for row in rows}
    missing = [highlight_id for highlight_id in ids if highlight_id not in by_id]
    if missing:
        raise ScopeResolutionError(f"highlight ID not found: {missing[0]}")
    for row in by_id.values():
        _active_document(conn, str(row["source_document_id"]))
        row["tags"] = json.loads(row.get("tags") or "[]") if isinstance(row.get("tags"), str) else []
    return [by_id[highlight_id] for highlight_id in ids]


def _resolve_highlights(
    conn: sqlite3.Connection,
    highlight_payload: dict[str, Any],
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    ids = _unique(_clean_string_list(highlight_payload.get("ids")))
    if not ids:
        raise ScopeResolutionError("Included highlights require durable highlight IDs")
    highlights = _load_highlights(conn, ids)
    doc_ids = _unique([str(item["source_document_id"]) for item in highlights])
    placeholders = ",".join("?" for _ in doc_ids)
    docs = conn.execute(
        f"""SELECT id, original_filename, file_hash, total_pages,
                   COALESCE(source_role, 'primary') AS source_role,
                   COALESCE(excluded_from_analysis, 0) AS excluded_from_analysis
            FROM source_documents
            WHERE id IN ({placeholders})""",
        doc_ids,
    ).fetchall()
    documents = [_document_payload(doc) for doc in docs]
    progress = conn.execute(
        f"SELECT * FROM reading_progress WHERE document_id IN ({placeholders})",
        doc_ids,
    ).fetchall()
    packet = compile_synthesis_packet(
        highlights,
        documents=documents,
        field_notes=[],
        reading_progress=[dict(row) for row in progress],
        compiled_at=datetime.now(timezone.utc).isoformat(),
        scope_document_id=doc_ids[0] if len(doc_ids) == 1 else None,
    )
    receipt_rows = []
    for row in highlights:
        receipt_rows.append({
            "id": row["id"],
            "kind": "reader_highlight",
            "text": row["selected_text"],
            "role": "supporting",
            "evidence_status": "durable_reader_highlight",
            "source_document_id": row["source_document_id"],
            "page": row["page"],
            "locator": row["source_locator"],
            "relevance": row["relevance"],
            "status": row["status"],
        })
    return receipt_rows, packet


def resolve_scope_for_provider(
    conn: sqlite3.Connection,
    scope: dict[str, Any],
) -> dict[str, object]:
    """Resolve a first-slice Working Scope against authoritative workspace data."""
    primary_payload = scope.get("primary") if isinstance(scope.get("primary"), dict) else scope
    if not isinstance(primary_payload, dict):
        raise ScopeResolutionError("Scope requires selected Reader text.")
    if not _clean_text(primary_payload.get("text")) and not _clean_text(primary_payload.get("locator")):
        raise ScopeResolutionError("Scope requires selected Reader text.")
    primary, primary_material = _resolve_reader_selection(conn, primary_payload)

    supporting_payload = scope.get("supporting") if isinstance(scope.get("supporting"), dict) else {}
    supported_keys = {"current_page", "highlights", "governing_question"}
    for key, value in supporting_payload.items():
        if key not in supported_keys and isinstance(value, dict) and value.get("include"):
            raise ScopeResolutionError(f"Unsupported Scope inclusion: {key}.")
    governing_payload = supporting_payload.get("governing_question")
    if isinstance(governing_payload, dict) and governing_payload.get("include"):
        raise ScopeResolutionError("Governing question is not Scope material for Perspective runs.")

    supporting: list[dict[str, object]] = []
    supporting_material: list[dict[str, object]] = []
    study_packet: dict[str, object] | None = None

    page_payload = supporting_payload.get("current_page")
    include_current_page = isinstance(page_payload, dict) and bool(page_payload.get("include"))
    if include_current_page:
        page_receipt, page_material = _resolve_current_page(
            conn,
            page_payload,
            fallback_doc_id=str(primary["source_document_id"]),
            fallback_page=int(primary["page"]),
        )
        supporting.append(page_receipt)
        supporting_material.append(page_material)

    highlight_payload = supporting_payload.get("highlights")
    include_highlights = isinstance(highlight_payload, dict) and bool(highlight_payload.get("include"))
    if include_highlights:
        highlights, study_packet = _resolve_highlights(conn, highlight_payload)
        supporting.extend(highlights)
        supporting_material.extend(highlights)

    return {
        "receipt_version": "resolved-scope:v1",
        "primary": primary,
        "supporting": supporting,
        "included": {
            "current_page": include_current_page,
            "highlights": include_highlights,
            "governing_question": False,
        },
        "excluded": {
            "governing_question": True,
            "current_page": not include_current_page,
            "highlights": not include_highlights,
            "entire_corpus": True,
            "all_notes": True,
            "accepted_interpretations": True,
            "other_documents": True,
        },
        "materialization": {
            "kind": "transient_scope_materialization",
            "status": "server_resolved",
            "compiler": "hermeneia.scope_resolution.resolve_scope_for_provider",
            "canonical_evidence_modified": False,
            "primary": primary_material,
            "supporting": supporting_material,
            "study_packet": study_packet,
        },
    }
