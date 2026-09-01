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
    id_prefix: str = "scope-ex",
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
                    f"{id_prefix}-{index}",
                    doc_id,
                    page,
                    f"block:{index}",
                    text,
                    f"page:{page}:block:{index}",
                    doc_id,
                    f"{id_prefix}-hash-{index}",
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
        "extraction_ids": [f"{id_prefix}-{index}" for index in range(1, len(blocks) + 1)],
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


def test_browser_preview_whitespace_can_differ_but_provider_material_is_authoritative(tmp_path):
    db_path = tmp_path / "scope.db"
    seed = _seed_scope_db(db_path)
    scope = _selection_scope(
        seed,
        text="beta begins. Middle line with Unicode ✓ and punctuation. Omega",
    )

    conn = _conn(db_path)
    try:
        receipt = resolve_scope_for_provider(conn, scope)
    finally:
        conn.close()

    authoritative = "beta begins.\n\nMiddle line with Unicode ✓ and punctuation.\n\nOmega"
    assert receipt["primary"]["text"] == authoritative
    assert receipt["materialization"]["primary"]["text"] == authoritative
    assert receipt["primary"]["text"] != scope["primary"]["text"]


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


def test_current_page_must_match_primary_document_and_page(tmp_path):
    db_path = tmp_path / "scope.db"
    seed = _seed_scope_db(db_path)
    other_doc = _seed_scope_db(
        db_path,
        doc_id="other-doc",
        page=2,
        id_prefix="other-ex",
        blocks=["Other document source text."],
    )
    other_page = _seed_scope_db(
        db_path,
        doc_id="scope-doc",
        page=3,
        id_prefix="page3-ex",
        blocks=["Same document, different page."],
    )
    primary_text = "beta begins.\n\nMiddle line with Unicode ✓ and punctuation.\n\nOmega"

    same_page_scope = _selection_scope(seed, text=primary_text)
    same_page_scope["supporting"] = {
        "current_page": {
            "include": True,
            "source_document_id": seed["doc_id"],
            "page": seed["page"],
        }
    }
    conn = _conn(db_path)
    try:
        assert resolve_scope_for_provider(conn, same_page_scope)["included"]["current_page"] is True
    finally:
        conn.close()

    other_doc_scope = _selection_scope(seed, text=primary_text)
    other_doc_scope["supporting"] = {
        "current_page": {
            "include": True,
            "source_document_id": other_doc["doc_id"],
            "page": other_doc["page"],
        }
    }
    conn = _conn(db_path)
    try:
        with pytest.raises(ScopeResolutionError, match="must match the primary Reader selection"):
            resolve_scope_for_provider(conn, other_doc_scope)
    finally:
        conn.close()

    other_page_scope = _selection_scope(seed, text=primary_text)
    other_page_scope["supporting"] = {
        "current_page": {
            "include": True,
            "source_document_id": seed["doc_id"],
            "page": other_page["page"],
        }
    }
    conn = _conn(db_path)
    try:
        with pytest.raises(ScopeResolutionError, match="must match the primary Reader selection"):
            resolve_scope_for_provider(conn, other_page_scope)
    finally:
        conn.close()


def test_reader_span_page_and_contradictory_provenance_fail_closed(tmp_path):
    db_path = tmp_path / "scope.db"
    seed = _seed_scope_db(db_path)
    text = "beta begins.\n\nMiddle line with Unicode ✓ and punctuation.\n\nOmega"

    wrong_page = _selection_scope(seed, text=text)
    wrong_page["primary"]["locator"] = _span_locator(
        page=99,
        start_block=0,
        start_offset=6,
        end_block=2,
        end_offset=5,
        locators=seed["locators"],
        extraction_ids=seed["extraction_ids"],
    )
    conn = _conn(db_path)
    try:
        with pytest.raises(ScopeResolutionError, match="locator page disagrees"):
            resolve_scope_for_provider(conn, wrong_page)
    finally:
        conn.close()

    contradictory = _selection_scope(seed, text=text)
    contradictory["primary"]["locator"] = _span_locator(
        page=int(seed["page"]),
        start_block=0,
        start_offset=6,
        end_block=2,
        end_offset=5,
        locators=["page:2:block:999", seed["locators"][1], seed["locators"][2]],
        extraction_ids=seed["extraction_ids"],
    )
    conn = _conn(db_path)
    try:
        with pytest.raises(ScopeResolutionError, match="cannot be mapped safely"):
            resolve_scope_for_provider(conn, contradictory)
    finally:
        conn.close()


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
    assert [item["text"] for item in receipt["materialization"]["supporting"]] == [
        "First durable mark.",
        "Second durable mark.",
    ]


def test_unranked_highlight_exact_text_is_lossless_material_with_derived_packet_provenance(tmp_path):
    db_path = tmp_path / "scope.db"
    seed = _seed_scope_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT INTO reader_highlights
               (id, source_document_id, source_role, page, source_locator,
                selected_text, relevance, tags, status, created_at, updated_at)
               VALUES
               ('hl-unranked', ?, 'primary', ?, ?, 'Exact unranked Reader mark.',
                'unclear', '[]', 'saved_highlight',
                '2026-08-29T12:03:00+00:00', '2026-08-29T12:03:00+00:00')""",
            (seed["doc_id"], seed["page"], seed["locators"][0]),
        )
        conn.commit()
    finally:
        conn.close()
    scope = _selection_scope(
        seed,
        text="beta begins.\n\nMiddle line with Unicode ✓ and punctuation.\n\nOmega",
    )
    scope["supporting"] = {"highlights": {"include": True, "ids": ["hl-unranked"]}}

    conn = _conn(db_path)
    try:
        receipt = resolve_scope_for_provider(conn, scope)
    finally:
        conn.close()

    assert receipt["materialization"]["supporting"][0]["id"] == "hl-unranked"
    assert receipt["materialization"]["supporting"][0]["text"] == "Exact unranked Reader mark."
    packet = receipt["materialization"]["study_packet"]
    assert packet["provenance"]["source_records"]["reader_highlight_ids"] == ["hl-unranked"]
    assert all(
        item.get("id") != "hl-unranked"
        for item in packet.get("ranked_highlights", [])
    )


def test_cross_document_highlight_fails_closed(tmp_path):
    db_path = tmp_path / "scope.db"
    seed = _seed_scope_db(db_path)
    other = _seed_scope_db(
        db_path,
        doc_id="other-doc",
        id_prefix="other-ex",
        blocks=["Other document source text."],
    )
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT INTO reader_highlights
               (id, source_document_id, source_role, page, source_locator,
                selected_text, relevance, tags, status, created_at, updated_at)
               VALUES
               ('hl-other-doc', ?, 'primary', ?, ?, 'Other document mark.',
                'supports', '[]', 'saved_highlight',
                '2026-08-29T12:04:00+00:00', '2026-08-29T12:04:00+00:00')""",
            (other["doc_id"], other["page"], other["locators"][0]),
        )
        conn.commit()
    finally:
        conn.close()
    scope = _selection_scope(
        seed,
        text="beta begins.\n\nMiddle line with Unicode ✓ and punctuation.\n\nOmega",
    )
    scope["supporting"] = {"highlights": {"include": True, "ids": ["hl-other-doc"]}}

    conn = _conn(db_path)
    try:
        with pytest.raises(ScopeResolutionError, match="primary Reader selection document"):
            resolve_scope_for_provider(conn, scope)
    finally:
        conn.close()


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
