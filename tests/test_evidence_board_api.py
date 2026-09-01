from __future__ import annotations

import sqlite3
from pathlib import Path
import json
from urllib.parse import quote

from hermeneia.scope_resolution import resolve_scope_for_provider
from hermeneia.storage.sqlite import SCHEMA_VERSION, SQLiteStore
from hermeneia.web.app import create_app


def _seed_board_db(db_path: Path) -> None:
    store = SQLiteStore(db_path)
    store.close()
    conn = sqlite3.connect(db_path)
    try:
        now = "2026-09-01T12:00:00+00:00"
        docs = [
            ("doc-a", "gatsby.pdf", "hash-a", 5, "primary"),
            ("doc-b", "letters.pdf", "hash-b", 3, "reference"),
        ]
        for doc_id, filename, file_hash, pages, role in docs:
            conn.execute(
                """INSERT INTO source_documents
                   (id, original_filename, file_hash, total_pages, registered_at,
                    compiler_version, excluded_from_analysis, source_role)
                   VALUES (?, ?, ?, ?, ?, 'test', 0, ?)""",
                (doc_id, filename, file_hash, pages, now, role),
            )
        extractions = [
            ("ex-a-1", "doc-a", 1, "block:1", "Canonical observation source text.", "page:1:block:1", "hash-ex-a-1"),
            ("ex-a-2", "doc-a", 2, "block:2", "Primary highlight source text.", "page:2:block:2", "hash-ex-a-2"),
            ("ex-b-1", "doc-b", 1, "block:1", "Reference source text.", "page:1:block:1", "hash-ex-b-1"),
        ]
        for extraction_id, doc_id, page, region, raw_text, locator, digest in extractions:
            conn.execute(
                """INSERT INTO source_extractions
                   (id, epistemic_class, document_id, page, region, raw_text,
                    parser, parser_version, coordinates, source_locator,
                    source_hash, hash, extracted_at)
                   VALUES (?, 'Evidence', ?, ?, ?, ?, 'test', 'test',
                           '{}', ?, ?, ?, ?)""",
                (extraction_id, doc_id, page, region, raw_text, locator, doc_id, digest, now),
            )
        conn.execute(
            """INSERT INTO observations
               (id, source_document_id, source_extraction_id, raw_text,
                source_locator, semantic_hash, page, paragraph, sentence, created_at)
               VALUES ('obs-a', 'doc-a', 'ex-a-1', 'Canonical observation source text.',
                       'page:1:block:1', 'sem-obs-a', 1, 1, 1, ?)""",
            (now,),
        )
        conn.execute(
            """INSERT INTO observation_reviews
               (id, observation_id, review_status, steward_note,
                reason_for_status, follow_up_needed, created_at, updated_at)
               VALUES ('rev-a', 'obs-a', 'approved', 'kept', 'useful', 0, ?, ?)""",
            (now, now),
        )
        highlights = [
            (
                "hl-a",
                "doc-a",
                "primary",
                2,
                "reader-span:v1:a",
                "Primary marked passage.",
                "A note.",
                "A question?",
                "supports",
                '["tag-a"]',
                "saved_highlight",
                5,
                "aspiration",
                "chapter-2",
            ),
            (
                "hl-b",
                "doc-a",
                "primary",
                3,
                "page:3:block:1",
                "Uncategorized marked passage.",
                None,
                None,
                "unclear",
                "[]",
                "observation_candidate",
                None,
                None,
                None,
            ),
            (
                "hl-c",
                "doc-b",
                "reference",
                1,
                "page:1:block:1",
                "Reference document mark.",
                None,
                "Reference question?",
                "complicates",
                "[]",
                "saved_highlight",
                3,
                " aspiration ",
                "cross-source",
            ),
            (
                "hl-dismissed",
                "doc-a",
                "primary",
                4,
                "page:4:block:1",
                "Dismissed mark.",
                None,
                None,
                "unclear",
                "[]",
                "dismissed",
                None,
                None,
                None,
            ),
        ]
        for row in highlights:
            conn.execute(
                """INSERT INTO reader_highlights
                   (id, source_document_id, source_role, page, source_locator,
                    selected_text, note_text, question_text, relevance, tags,
                    status, rank, theme_bucket, evidence_bucket, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*row, now, now),
            )
        conn.execute(
            """INSERT INTO investigation_log
               (id, lane, understanding, pressing_questions, source_document_id,
                page, governing_question, created_at)
               VALUES ('fn-a', 'corpus', 'Field understanding.', 'What remains?',
               'doc-a', 2, 'How does attention accumulate?', ?)""",
            (now,),
        )
        conn.execute(
            """INSERT INTO investigation_log
               (id, lane, understanding, pressing_questions, source_document_id,
                page, governing_question, created_at)
               VALUES ('fn-instrument', 'instrument', 'Instrument note.', 'Should stay out?',
                       'doc-a', 2, 'How does attention accumulate?', ?)""",
            (now,),
        )
        conn.commit()
    finally:
        conn.close()


def _counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        return {
            name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            for name in [
                "source_documents",
                "source_extractions",
                "observations",
                "reader_highlights",
                "investigation_log",
                "interpretations",
                "narrative_blueprints",
            ]
        }
    finally:
        conn.close()


def test_evidence_board_inventory_counts_and_record_types(tmp_path):
    db_path = tmp_path / "board.db"
    _seed_board_db(db_path)
    before = _counts(db_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get("/api/evidence-board?current_document_id=doc-a&current_page=2")

    assert response.status_code == 200
    body = response.get_json()
    assert body["counts"] == {
        "highlights": 3,
        "dismissed_highlights": 1,
        "field_notes": 1,
        "observations": 1,
        "question_bearing_records": 3,
        "theme_buckets": 1,
        "evidence_buckets": 2,
        "uncategorized_highlights": 1,
        "deferred_instrument_notes": 1,
    }
    assert {item["id"] for item in body["highlights"]} == {"hl-a", "hl-b", "hl-c"}
    assert "hl-dismissed" not in {item["id"] for item in body["highlights"]}
    assert {item["id"] for item in body["field_notes"]} == {"fn-a"}
    assert body["field_notes"][0]["record_type"] == "field_note"
    assert body["field_notes"][0]["understanding"] == "Field understanding."
    assert body["field_notes"][0]["origin_status"] == "not_recorded"
    assert "authorship" not in body["field_notes"][0]
    assert body["observations"][0]["record_type"] == "canonical_observation"
    assert body["observations"][0]["review_status"] == "approved"
    assert "Count of Reader highlights with question_text plus corpus Field Notes" in body["question_count_semantics"]
    assert body["canonical_evidence_modified"] is False
    assert _counts(db_path) == before


def test_evidence_board_bucket_groupings_are_derived_from_highlight_fields(tmp_path):
    db_path = tmp_path / "board.db"
    _seed_board_db(db_path)
    client = create_app(db_path=db_path).test_client()

    body = client.get("/api/evidence-board?current_document_id=doc-a").get_json()

    assert body["uncategorized_definition"] == (
        "Reader highlights with no theme_bucket and no evidence_bucket."
    )
    assert body["theme_buckets"] == [
        {
            "bucket": "aspiration",
            "kind": "theme_bucket",
            "count": 2,
            "highlight_ids": ["hl-a", "hl-c"],
            "projection": "derived grouping over reader_highlights.theme_bucket",
        }
    ]
    assert {bucket["bucket"]: bucket["highlight_ids"] for bucket in body["evidence_buckets"]} == {
        "chapter-2": ["hl-a"],
        "cross-source": ["hl-c"],
    }


def test_evidence_board_field_notes_are_corpus_lane_only(tmp_path):
    db_path = tmp_path / "board.db"
    _seed_board_db(db_path)
    client = create_app(db_path=db_path).test_client()

    body = client.get("/api/evidence-board?current_document_id=doc-a").get_json()

    assert [item["lane"] for item in body["field_notes"]] == ["corpus"]
    assert "fn-instrument" not in {item["id"] for item in body["field_notes"]}
    assert body["counts"]["deferred_instrument_notes"] == 1


def test_evidence_board_marks_cross_document_highlights_ineligible_for_current_scope(tmp_path):
    db_path = tmp_path / "board.db"
    _seed_board_db(db_path)
    client = create_app(db_path=db_path).test_client()

    body = client.get("/api/evidence-board?current_document_id=doc-a").get_json()
    by_id = {item["id"]: item for item in body["highlights"]}

    assert by_id["hl-a"]["scope_eligible"] is True
    assert by_id["hl-b"]["scope_eligible"] is True
    assert by_id["hl-c"]["scope_eligible"] is False
    assert "Different source document" in by_id["hl-c"]["scope_ineligibility_reason"]


def test_evidence_board_selected_highlights_feed_existing_scope_resolver(tmp_path):
    db_path = tmp_path / "board.db"
    _seed_board_db(db_path)
    client = create_app(db_path=db_path).test_client()

    body = client.get("/api/evidence-board?current_document_id=doc-a").get_json()
    selected_ids = [
        item["id"]
        for item in body["highlights"]
        if item["scope_eligible"] and item["id"] in {"hl-a", "hl-b"}
    ]
    span = {
        "coordinate_space": "reader_projection",
        "page": 2,
        "start": {
            "block_index": 0,
            "source_locator": "page:2:block:2",
            "source_locators": ["page:2:block:2"],
            "extraction_ids": ["ex-a-2"],
            "offset": 0,
        },
        "end": {
            "block_index": 0,
            "source_locator": "page:2:block:2",
            "source_locators": ["page:2:block:2"],
            "extraction_ids": ["ex-a-2"],
            "offset": len("Primary highlight source text."),
        },
        "source_locators": ["page:2:block:2"],
        "extraction_ids": ["ex-a-2"],
    }
    scope = {
        "primary": {
            "kind": "reader_selection",
            "text": "Primary highlight source text.",
            "source_document_id": "doc-a",
            "page": 2,
            "locator": "reader-span:v1:" + quote(json.dumps(span, separators=(",", ":"))),
        },
        "supporting": {"highlights": {"include": True, "ids": selected_ids}},
    }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        receipt = resolve_scope_for_provider(conn, scope)
    finally:
        conn.close()

    assert selected_ids == ["hl-a", "hl-b"]
    assert [item["id"] for item in receipt["supporting"]] == ["hl-a", "hl-b"]
    assert [item["text"] for item in receipt["materialization"]["supporting"]] == [
        "Primary marked passage.",
        "Uncategorized marked passage.",
    ]
    assert _counts(db_path)["reader_highlights"] == 4
    assert SCHEMA_VERSION == 17
