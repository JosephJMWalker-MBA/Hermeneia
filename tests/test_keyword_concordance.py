from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from hermeneia.compiler.compiler import Compiler
from hermeneia.concordance import (
    MATCHING_MODE,
    SEARCH_TEXT_SOURCE,
    literal_occurrence_spans,
)
from hermeneia.storage.sqlite import SCHEMA_VERSION, SQLiteStore
from hermeneia.web.app import create_app


GATSBY_PDF = Path(__file__).parent.parent / "examples" / "gatsby.pdf"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fresh_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "concordance.db"
    SQLiteStore(db_path).close()
    return db_path


def _insert_doc(
    conn: sqlite3.Connection,
    doc_id: str,
    *,
    filename: str,
    total_pages: int = 10,
    source_role: str = "primary",
    excluded: int = 0,
) -> None:
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, filename, doc_id, total_pages, _now(), "test", source_role, excluded),
    )


def _insert_observation(
    conn: sqlite3.Connection,
    *,
    obs_id: str,
    doc_id: str,
    extraction_id: str,
    text: str,
    page: int,
    paragraph: int,
    sentence: int,
    locator: str | None = None,
    normalized_text: str | None = None,
) -> None:
    locator = locator or f"page:{page}:block:{paragraph}:sentence:{sentence}"
    conn.execute(
        """INSERT INTO source_extractions
           (id, document_id, page, region, raw_text, parser, parser_version,
            coordinates, source_locator, source_hash, hash, extracted_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            extraction_id,
            doc_id,
            page,
            f"block:{paragraph}",
            text,
            "test",
            "1",
            "{}",
            locator,
            doc_id,
            extraction_id,
            _now(),
        ),
    )
    conn.execute(
        """INSERT INTO observations
           (id, epistemic_class, source_document_id, source_extraction_id,
            raw_text, source_locator, semantic_hash, page, paragraph, sentence,
            created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            obs_id,
            "Evidence",
            doc_id,
            extraction_id,
            text,
            locator,
            f"hash-{obs_id}",
            page,
            paragraph,
            sentence,
            _now(),
        ),
    )
    if normalized_text is not None:
        conn.execute(
            """INSERT INTO observation_derived
               (observation_id, normalized_text, sentence_tokens, whitespace_map,
                derivation_version, derived_at)
               VALUES (?,?,?,?,?,?)""",
            (obs_id, normalized_text, "[]", "[]", "test", _now()),
        )


def _seed(
    tmp_path: Path,
    rows: list[dict],
    *,
    docs: list[dict] | None = None,
) -> Path:
    db_path = _fresh_db(tmp_path)
    conn = sqlite3.connect(db_path)
    for doc in docs or [{"doc_id": "doc-a", "filename": "primary.pdf"}]:
        _insert_doc(conn, **doc)
    for row in rows:
        _insert_observation(conn, **row)
    conn.commit()
    conn.close()
    return db_path


def _search(db_path: Path, query: str, *, limit: int | None = None) -> dict:
    params = {"q": query}
    if limit is not None:
        params["limit"] = str(limit)
    return create_app(db_path=db_path).test_client().get(
        f"/api/search?{urlencode(params)}"
    ).get_json()


def _assert_distribution_invariants(body: dict) -> None:
    assert body["occurrence_count"] == len(body["occurrences"])
    result_occurrences = sum(row["occurrence_count"] for row in body["results"])
    if not body["results_truncated"]:
        assert body["occurrence_count"] == result_occurrences
    distribution_total = sum(
        doc["occurrence_count"]
        for doc in body["distribution"]["documents"]
    )
    assert body["occurrence_count"] == distribution_total
    for doc in body["distribution"]["documents"]:
        assert doc["occurrence_count"] == sum(
            page["occurrence_count"]
            for page in doc["pages"]
        )


def test_repeated_phrase_twice_in_one_passage_counts_two_occurrences(tmp_path: Path) -> None:
    db = _seed(tmp_path, [{
        "obs_id": "obs-1",
        "doc_id": "doc-a",
        "extraction_id": "ext-1",
        "text": "green light and another green light",
        "page": 2,
        "paragraph": 1,
        "sentence": 1,
    }])

    body = _search(db, "green light")

    assert body["count"] == body["passage_count"] == 1
    assert body["occurrence_count"] == 2
    assert body["page_count"] == 1
    assert body["document_count"] == 1
    assert body["section_count"] is None
    assert body["section_count_available"] is False
    assert body["matching"] == {
        "mode": MATCHING_MODE,
        "search_text_source": SEARCH_TEXT_SOURCE,
        "result_unit": "observation",
        "cross_observation": False,
        "overlapping": False,
    }
    assert body["results"][0]["occurrence_count"] == 2
    assert [occ["matched_text"] for occ in body["results"][0]["occurrences"]] == [
        "green light",
        "green light",
    ]
    _assert_distribution_invariants(body)


def test_repeated_phrase_across_passages_counts_passages_and_occurrences(tmp_path: Path) -> None:
    db = _seed(tmp_path, [
        {
            "obs_id": "obs-1",
            "doc_id": "doc-a",
            "extraction_id": "ext-1",
            "text": "one green light",
            "page": 1,
            "paragraph": 1,
            "sentence": 1,
        },
        {
            "obs_id": "obs-2",
            "doc_id": "doc-a",
            "extraction_id": "ext-2",
            "text": "another green light",
            "page": 3,
            "paragraph": 2,
            "sentence": 1,
        },
    ])

    body = _search(db, "green light")

    assert body["count"] == body["passage_count"] == 2
    assert body["occurrence_count"] == 2
    assert body["page_count"] == 2
    _assert_distribution_invariants(body)


def test_twice_in_one_passage_plus_once_in_another(tmp_path: Path) -> None:
    db = _seed(tmp_path, [
        {
            "obs_id": "obs-1",
            "doc_id": "doc-a",
            "extraction_id": "ext-1",
            "text": "green light and green light",
            "page": 1,
            "paragraph": 1,
            "sentence": 1,
        },
        {
            "obs_id": "obs-2",
            "doc_id": "doc-a",
            "extraction_id": "ext-2",
            "text": "final green light",
            "page": 2,
            "paragraph": 1,
            "sentence": 1,
        },
    ])

    body = _search(db, "green light")

    assert body["passage_count"] == 2
    assert body["occurrence_count"] == 3
    _assert_distribution_invariants(body)


def test_capitalization_and_punctuation_adjacency_match_literal_phrase(tmp_path: Path) -> None:
    db = _seed(tmp_path, [{
        "obs_id": "obs-1",
        "doc_id": "doc-a",
        "extraction_id": "ext-1",
        "text": "Green Light, then (GREEN LIGHT), then green light.",
        "page": 1,
        "paragraph": 1,
        "sentence": 1,
    }])

    body = _search(db, "green light")

    assert body["occurrence_count"] == 3
    assert [occ["matched_text"] for occ in body["occurrences"]] == [
        "Green Light",
        "GREEN LIGHT",
        "green light",
    ]


def test_unicode_behavior_follows_current_normalized_search_representation(tmp_path: Path) -> None:
    db = _seed(tmp_path, [{
        "obs_id": "obs-1",
        "doc_id": "doc-a",
        "extraction_id": "ext-1",
        "text": "He said “don’t stop.”",
        "normalized_text": 'He said "don\'t stop."',
        "page": 1,
        "paragraph": 1,
        "sentence": 1,
    }])

    body = _search(db, "don't")

    assert body["occurrence_count"] == 1
    assert body["results"][0]["text"] == 'He said "don\'t stop."'
    assert body["results"][0]["canonical_text"] == "He said “don’t stop.”"
    assert body["occurrences"][0]["matched_text"] == "don't"


def test_cross_observation_phrase_is_not_concatenated(tmp_path: Path) -> None:
    db = _seed(tmp_path, [
        {
            "obs_id": "obs-1",
            "doc_id": "doc-a",
            "extraction_id": "ext-1",
            "text": "green",
            "page": 1,
            "paragraph": 1,
            "sentence": 1,
        },
        {
            "obs_id": "obs-2",
            "doc_id": "doc-a",
            "extraction_id": "ext-2",
            "text": "light",
            "page": 1,
            "paragraph": 1,
            "sentence": 2,
        },
    ])

    body = _search(db, "green light")

    assert body["occurrence_count"] == 0
    assert body["passage_count"] == 0
    assert body["matching"]["cross_observation"] is False


def test_excluded_documents_do_not_affect_any_concordance_counts(tmp_path: Path) -> None:
    db = _seed(
        tmp_path,
        [
            {
                "obs_id": "obs-1",
                "doc_id": "doc-a",
                "extraction_id": "ext-1",
                "text": "green light",
                "page": 1,
                "paragraph": 1,
                "sentence": 1,
            },
            {
                "obs_id": "obs-2",
                "doc_id": "doc-x",
                "extraction_id": "ext-x",
                "text": "green light green light",
                "page": 1,
                "paragraph": 1,
                "sentence": 1,
            },
        ],
        docs=[
            {"doc_id": "doc-a", "filename": "primary.pdf"},
            {"doc_id": "doc-x", "filename": "excluded.pdf", "excluded": 1},
        ],
    )

    body = _search(db, "green light")

    assert body["occurrence_count"] == 1
    assert body["passage_count"] == 1
    assert body["document_count"] == 1
    assert {occ["source_document_id"] for occ in body["occurrences"]} == {"doc-a"}
    _assert_distribution_invariants(body)


def test_same_page_number_in_multiple_documents_counts_distinct_page_hits(tmp_path: Path) -> None:
    db = _seed(
        tmp_path,
        [
            {
                "obs_id": "obs-a",
                "doc_id": "doc-a",
                "extraction_id": "ext-a",
                "text": "green light",
                "page": 2,
                "paragraph": 1,
                "sentence": 1,
            },
            {
                "obs_id": "obs-b",
                "doc_id": "doc-b",
                "extraction_id": "ext-b",
                "text": "green light",
                "page": 2,
                "paragraph": 1,
                "sentence": 1,
            },
        ],
        docs=[
            {"doc_id": "doc-a", "filename": "a.pdf"},
            {"doc_id": "doc-b", "filename": "b.pdf", "source_role": "commentary"},
        ],
    )

    body = _search(db, "green light")

    assert body["occurrence_count"] == 2
    assert body["page_count"] == 2
    assert body["document_count"] == 2
    assert {
        (occ["source_document_id"], occ["page"])
        for occ in body["occurrences"]
    } == {("doc-a", 2), ("doc-b", 2)}


def test_result_limit_truncates_passages_not_global_occurrence_evidence(tmp_path: Path) -> None:
    rows = [
        {
            "obs_id": f"obs-{idx}",
            "doc_id": "doc-a",
            "extraction_id": f"ext-{idx}",
            "text": "green light green light" if idx == 1 else "green light",
            "page": idx,
            "paragraph": 1,
            "sentence": 1,
        }
        for idx in range(1, 5)
    ]
    db = _seed(tmp_path, rows)

    body = _search(db, "green light", limit=2)

    assert len(body["results"]) == 2
    assert body["results_truncated"] is True
    assert body["passage_count"] == 4
    assert body["count"] == 4
    assert body["occurrence_count"] == 5
    assert len(body["occurrences"]) == 5
    assert sum(doc["occurrence_count"] for doc in body["distribution"]["documents"]) == 5


def test_every_occurrence_is_addressable_to_source_provenance(tmp_path: Path) -> None:
    db = _seed(tmp_path, [{
        "obs_id": "obs-1",
        "doc_id": "doc-a",
        "extraction_id": "ext-1",
        "text": "green light",
        "page": 7,
        "paragraph": 3,
        "sentence": 2,
        "locator": "page:7:block:3:sentence:2",
    }])

    body = _search(db, "green light")
    occurrence = body["occurrences"][0]

    assert occurrence == {
        "source_document_id": "doc-a",
        "observation_id": "obs-1",
        "source_extraction_id": "ext-1",
        "source_locator": "page:7:block:3:sentence:2",
        "document_name": "primary.pdf",
        "source_role": "primary",
        "page": 7,
        "paragraph": 3,
        "sentence": 2,
        "start": 0,
        "end": 11,
        "matched_text": "green light",
    }


def test_gatsby_green_light_matches_mechanical_searchable_representation_oracle(tmp_path: Path) -> None:
    db_path = tmp_path / "gatsby.db"
    compiler = Compiler(db_path=db_path, build_dir=tmp_path / "build")
    compiler.compile(GATSBY_PDF)
    compiler.close()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT o.id, o.source_document_id, o.source_extraction_id,
               o.source_locator, o.page, o.paragraph, o.sentence,
               COALESCE(od.normalized_text, o.raw_text) AS searchable_text
        FROM observations o
        LEFT JOIN observation_derived od ON od.observation_id = o.id
        JOIN source_documents sd ON sd.id = o.source_document_id
        WHERE COALESCE(sd.excluded_from_analysis, 0) = 0
        ORDER BY sd.original_filename, o.page, o.paragraph, o.sentence
        """
    ).fetchall()
    oracle_passages = [
        row for row in rows
        if literal_occurrence_spans(row["searchable_text"], "green light")
    ]
    oracle_occurrences = [
        (row, occurrence)
        for row in rows
        for occurrence in literal_occurrence_spans(row["searchable_text"], "green light")
    ]
    source_rows = conn.execute(
        """
        SELECT raw_text
        FROM source_extractions
        WHERE document_id IN (SELECT id FROM source_documents WHERE excluded_from_analysis = 0)
        """
    ).fetchall()
    source_occurrence_count = sum(
        len(literal_occurrence_spans(row["raw_text"], "green light"))
        for row in source_rows
    )
    schema_version = conn.execute(
        "SELECT MAX(version) FROM schema_version"
    ).fetchone()[0]
    conn.close()

    body = _search(db_path, "green light", limit=3)

    assert schema_version == SCHEMA_VERSION == 17
    assert body["occurrence_count"] == len(oracle_occurrences)
    assert body["passage_count"] == len(oracle_passages)
    assert body["count"] == body["passage_count"]
    assert body["page_count"] == len({
        (row["source_document_id"], row["page"])
        for row in oracle_passages
    })
    assert body["document_count"] == len({
        row["source_document_id"]
        for row in oracle_passages
    })
    assert len(body["occurrences"]) == body["occurrence_count"]
    assert body["results_truncated"] is True
    assert source_occurrence_count >= body["occurrence_count"]
    _assert_distribution_invariants(body)
