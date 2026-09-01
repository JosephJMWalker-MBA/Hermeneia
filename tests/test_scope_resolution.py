from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from urllib.parse import quote

import pytest

from hermeneia.scope_resolution import ScopeResolutionError, resolve_scope_for_provider
from hermeneia.storage.sqlite import SQLiteStore


def _span_locator(
    *,
    page: int = 2,
    start_block: int = 0,
    start_offset: int = 0,
    end_block: int = 0,
    end_offset: int = 0,
    locators: list[str],
    extraction_ids: list[str],
) -> str:
    span = {
        "coordinate_space": "reader_projection",
        "page": page,
        "start": {
            "block_index": start_block,
            "source_locator": locators[0],
            "source_locators": [locators[0]],
            "extraction_ids": [extraction_ids[0]],
            "offset": start_offset,
        },
        "end": {
            "block_index": end_block,
            "source_locator": locators[-1],
            "source_locators": [locators[-1]],
            "extraction_ids": [extraction_ids[-1]],
            "offset": end_offset,
        },
        "source_locators": locators,
        "extraction_ids": extraction_ids,
    }
    return "reader-span:v1:" + quote(json.dumps(span, separators=(",", ":")))


def _seed_scope_db(
    db_path: Path,
    *,
    doc_id: str = "scope-doc",
    page: int = 2,
    blocks: list[str] | None = None,
    excluded: bool = False,
) -> dict[str, object]:
    blocks = blocks or [
        "Alpha beta begins.",
        "Middle line with Unicode ✓ and punctuation.",
        "Omega closes the selected material.",
    ]
    store = SQLiteStore(db_path)
    store.close()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT OR IGNORE INTO source_documents
               (id, original_filename, file_hash, total_pages, registered_at,
                compiler_version, excluded_from_analysis, source_role)
               VALUES (?, 'scope.pdf', ?, ?, '2026-08-29T12:00:00+00:00',
                       'test', ?, 'primary')""",
            (doc_id, doc_id, page, int(excluded)),
        )
        for index, text in enumerate(blocks, start=1):
            conn.execute(
                """INSERT OR IGNORE INTO source_extractions
                   (id, epistemic_class, document_id, page, region, raw_text,
                    parser, parser_version, coordinates, source_locator, source_hash,
                    hash, extracted_at)
                   VALUES (?, 'Evidence', ?, ?, ?, ?, 'test-parser', 'test',
                           '{}', ?, ?, ?, '2026-08-29T12:00:00+00:00')""",
                (
                    f"scope-ex-{index}",
                    doc_id,
                    page,
                    f"block:{index}",
                    text,
                    f"page:{page}:block:{index}",
                    doc_id,
                    f"scope-hash-{index}",
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return {
        "doc_id": doc_id,
        "page": page,
        "blocks": blocks,
        "locators": [f"page:{page}:block:{index}" for index in range(1, len(blocks) + 1)],
        "extraction_ids": [f"scope-ex-{index}" for index in range(1, len(blocks) + 1)],
    }


def _selection_scope(seed: dict[str, object], *, text: str) -> dict[str, object]:
    blocks = seed["blocks"]
    assert isinstance(blocks, list)
    locators = seed["locators"]
    extraction_ids = seed["extraction_ids"]
    assert isinstance(locators, list)
    assert isinstance(extraction_ids, list)
    return {
        "primary": {
            "kind": "reader_selection",
            "text": text,
            "source_document_id": seed["doc_id"],
            "page": seed["page"],
            "locator": _span_locator(
                page=int(seed["page"]),
                start_block=0,
                start_offset=6,
                end_block=2,
                end_offset=5,
                locators=locators,
                extraction_ids=extraction_ids,
            ),
        },
    }


def _conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def test_reader_selection_resolves_to_authoritative_projected_source(tmp_path):
    db_path = tmp_path / "scope.db"
    seed = _seed_scope_db(db_path)
    scope = _selection_scope(
        seed,
        text="beta begins.\n\nMiddle line with Unicode ✓ and punctuation.\n\nOmega",
    )

    conn = _conn(db_path)
    try:
        receipt = resolve_scope_for_provider(conn, scope)
    finally:
        conn.close()

    assert receipt["receipt_version"] == "resolved-scope:v1"
    assert receipt["primary"]["text"] == (
        "beta begins.\n\nMiddle line with Unicode ✓ and punctuation.\n\nOmega"
    )
    assert receipt["primary"]["source_metadata_origin"] == "server_resolved_reader_projection"
    assert receipt["primary"]["source_locators"] == seed["locators"]
    assert receipt["primary"]["extraction_ids"] == seed["extraction_ids"]
    assert receipt["materialization"]["primary"]["text"] == receipt["primary"]["text"]
    assert receipt["materialization"]["canonical_evidence_modified"] is False


def test_tampered_client_selection_text_fails_closed(tmp_path):
    db_path = tmp_path / "scope.db"
    seed = _seed_scope_db(db_path)
    scope = _selection_scope(seed, text="Browser-invented text.")

    conn = _conn(db_path)
    try:
        with pytest.raises(ScopeResolutionError, match="disagrees with authoritative Reader source"):
            resolve_scope_for_provider(conn, scope)
    finally:
        conn.close()


def test_current_page_is_resolved_server_side(tmp_path):
    db_path = tmp_path / "scope.db"
    seed = _seed_scope_db(db_path)
    scope = _selection_scope(
        seed,
        text="beta begins.\n\nMiddle line with Unicode ✓ and punctuation.\n\nOmega",
    )
    scope["supporting"] = {
        "current_page": {
            "include": True,
            "source_document_id": seed["doc_id"],
            "page": seed["page"],
        }
    }

    conn = _conn(db_path)
    try:
        receipt = resolve_scope_for_provider(conn, scope)
    finally:
        conn.close()

    page = receipt["supporting"][0]
    assert page["kind"] == "current_page"
    assert page["text"] == "\n\n".join(seed["blocks"])
    assert page["source_metadata_origin"] == "server_resolved_reader_projection"
    assert "Browser" not in page["text"]


def test_invalid_locator_and_excluded_document_fail_closed(tmp_path):
    db_path = tmp_path / "scope.db"
    seed = _seed_scope_db(db_path)
    bad_locator_scope = _selection_scope(seed, text="anything")
    bad_locator_scope["primary"]["locator"] = "reader-span:v1:%7Bnot-json"

    conn = _conn(db_path)
    try:
        with pytest.raises(ScopeResolutionError, match="valid reader-span locator"):
            resolve_scope_for_provider(conn, bad_locator_scope)
    finally:
        conn.close()

    excluded_db = tmp_path / "excluded.db"
    excluded = _seed_scope_db(excluded_db, excluded=True)
    excluded_scope = _selection_scope(
        excluded,
        text="beta begins.\n\nMiddle line with Unicode ✓ and punctuation.\n\nOmega",
    )
    conn = _conn(excluded_db)
    try:
        with pytest.raises(ScopeResolutionError, match="excluded_from_analysis"):
            resolve_scope_for_provider(conn, excluded_scope)
    finally:
        conn.close()


def test_durable_highlight_ids_materialize_exact_records_and_study_packet(tmp_path):
    db_path = tmp_path / "scope.db"
    seed = _seed_scope_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT INTO reader_highlights
               (id, source_document_id, source_role, page, source_locator,
                selected_text, relevance, tags, status, created_at, updated_at)
               VALUES
               ('hl-b', ?, 'primary', ?, ?, 'Second durable mark.', 'supports', '[]',
                'saved_highlight', '2026-08-29T12:02:00+00:00', '2026-08-29T12:02:00+00:00'),
               ('hl-a', ?, 'primary', ?, ?, 'First durable mark.', 'complicates', '[]',
                'saved_highlight', '2026-08-29T12:01:00+00:00', '2026-08-29T12:01:00+00:00')""",
            (
                seed["doc_id"], seed["page"], seed["locators"][1],
                seed["doc_id"], seed["page"], seed["locators"][0],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    scope = _selection_scope(
        seed,
        text="beta begins.\n\nMiddle line with Unicode ✓ and punctuation.\n\nOmega",
    )
    scope["supporting"] = {"highlights": {"include": True, "ids": ["hl-a", "hl-b"]}}

    conn = _conn(db_path)
    try:
        receipt = resolve_scope_for_provider(conn, scope)
    finally:
        conn.close()

    highlights = [item for item in receipt["supporting"] if item["kind"] == "reader_highlight"]
    assert [item["id"] for item in highlights] == ["hl-a", "hl-b"]
    assert [item["locator"] for item in highlights] == [seed["locators"][0], seed["locators"][1]]
    packet = receipt["materialization"]["study_packet"]
    assert packet["packet_type"] == "study-synthesis-packet-v1"
    assert packet["provenance"]["source_records"]["reader_highlight_ids"] == ["hl-a", "hl-b"]


def test_missing_highlight_id_fails_closed(tmp_path):
    db_path = tmp_path / "scope.db"
    seed = _seed_scope_db(db_path)
    scope = _selection_scope(
        seed,
        text="beta begins.\n\nMiddle line with Unicode ✓ and punctuation.\n\nOmega",
    )
    scope["supporting"] = {"highlights": {"include": True, "ids": ["missing-highlight"]}}

    conn = _conn(db_path)
    try:
        with pytest.raises(ScopeResolutionError, match="highlight ID not found"):
            resolve_scope_for_provider(conn, scope)
    finally:
        conn.close()
