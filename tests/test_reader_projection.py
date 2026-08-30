"""Reader-only text projection tests.

Canonical SourceExtraction and Observation text remains untouched. These tests
cover only the disposable presentation returned by the Reader API.
"""
from __future__ import annotations

import copy
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app
from hermeneia.web.reader_projection import (
    ReaderProjectionCoverageError,
    project_reader_extractions,
    reader_projection_coverage,
)


def _extraction(
    extraction_id: str,
    page: int,
    block: int,
    raw_text: str,
) -> dict[str, object]:
    return {
        "id": extraction_id,
        "page": page,
        "region": f"block:{block}",
        "raw_text": raw_text,
        "source_locator": f"page:{page}:block:{block}",
    }


def _compact_whitespace(text: object) -> str:
    return "".join(str(text or "").split())


def test_drop_cap_projection_merges_display_text_and_preserves_canonical_blocks() -> None:
    canonical = [
        _extraction("ext-I", 3, 2, "I"),
        _extraction(
            "ext-rest",
            3,
            3,
            "n my younger and more vulnerable years my father gave me some advice...",
        ),
    ]
    before = copy.deepcopy(canonical)

    projected = project_reader_extractions(canonical)

    assert canonical == before
    assert len(projected) == 1
    assert (
        projected[0]["text"]
        == "In my younger and more vulnerable years my father gave me some advice..."
    )
    assert projected[0]["reader_projection"] == {
        "kind": "drop_cap_merge",
        "source_extraction_ids": ["ext-I", "ext-rest"],
        "source_locators": ["page:3:block:2", "page:3:block:3"],
        "display_source_spans": [
            {
                "source_extraction_id": "ext-I",
                "source_locator": "page:3:block:2",
                "start": 0,
                "end": 1,
            },
            {
                "source_extraction_id": "ext-rest",
                "source_locator": "page:3:block:3",
                "start": 1,
                "end": 72,
            },
        ],
    }
    assert projected[0]["canonical_extractions"] == canonical


@pytest.mark.parametrize(
    ("previous", "following"),
    [
        (_extraction("a", 3, 2, "I."), _extraction("b", 3, 3, "n continuation")),
        (_extraction("a", 3, 2, "I"), _extraction("b", 3, 3, "Next paragraph")),
        (_extraction("a", 3, 2, "I"), _extraction("b", 4, 3, "n next page")),
        (_extraction("a", 3, 2, "I"), _extraction("b", 3, 4, "n nonadjacent")),
    ],
)
def test_reader_projection_does_not_merge_unsafe_pairs(
    previous: dict[str, object],
    following: dict[str, object],
) -> None:
    projected = project_reader_extractions([previous, following])

    assert len(projected) == 2
    assert [item["text"] for item in projected] == [
        previous["raw_text"],
        following["raw_text"],
    ]
    assert [item["source_extraction_id"] for item in projected] == [
        previous["id"],
        following["id"],
    ]
    assert all(item["reader_projection"] is None for item in projected)


def test_soft_wrap_normalization_is_reader_only_and_accounted_as_incorporated() -> None:
    canonical = [
        _extraction(
            "ext-soft",
            12,
            4,
            "The sentence breaks\nacross layout lines with inter-\npretation intact.",
        ),
    ]
    before = copy.deepcopy(canonical)

    projected = project_reader_extractions(canonical)
    coverage = reader_projection_coverage(canonical, projected)

    assert canonical == before
    assert projected[0]["text"] == (
        "The sentence breaks across layout lines with inter-pretation intact."
    )
    assert projected[0]["reader_projection"] == {
        "kind": "soft_wrap_normalization",
        "source_extraction_ids": ["ext-soft"],
        "source_locators": ["page:12:block:4"],
        "display_source_spans": [
            {
                "source_extraction_id": "ext-soft",
                "source_locator": "page:12:block:4",
                "start": 0,
                "end": 68,
            },
        ],
    }
    assert projected[0]["canonical_extractions"] == canonical
    assert coverage[0]["status"] == "incorporated"
    assert coverage[0]["reason"] == "soft_wrap_normalization"
    assert _compact_whitespace(projected[0]["text"]) == _compact_whitespace(
        canonical[0]["raw_text"]
    )


def test_soft_wrap_preserves_semantic_blank_line_boundary() -> None:
    canonical = [
        _extraction(
            "ext-paras",
            5,
            2,
            "First paragraph wraps\ninside itself.\n\nSecond paragraph stays separate.",
        ),
    ]

    projected = project_reader_extractions(canonical)

    assert projected[0]["text"] == (
        "First paragraph wraps inside itself.\n\nSecond paragraph stays separate."
    )
    assert projected[0]["reader_projection"]["kind"] == "soft_wrap_normalization"


def test_prose_continuation_merges_safe_numeric_order_without_requiring_consecutive_blocks() -> None:
    canonical = [
        _extraction(
            "ext-08",
            39,
            8,
            "Elias listened while the agency described a person whose client had not yet ",
        ),
        _extraction("ext-10", 39, 10, "become a bestseller but had already begun charging"),
        _extraction("ext-11", 39, 11, "as if he had."),
    ]
    before = copy.deepcopy(canonical)

    projected = project_reader_extractions(canonical)
    coverage = reader_projection_coverage(canonical, projected)

    assert canonical == before
    assert len(projected) == 1
    assert projected[0]["text"] == (
        "Elias listened while the agency described a person whose client had not yet "
        "become a bestseller but had already begun charging as if he had."
    )
    assert projected[0]["reader_projection"] == {
        "kind": "prose_continuation_merge",
        "source_extraction_ids": ["ext-08", "ext-10", "ext-11"],
        "source_locators": [
            "page:39:block:8",
            "page:39:block:10",
            "page:39:block:11",
        ],
        "display_source_spans": [
            {
                "source_extraction_id": "ext-08",
                "source_locator": "page:39:block:8",
                "start": 0,
                "end": 75,
            },
            {
                "source_extraction_id": "ext-10",
                "source_locator": "page:39:block:10",
                "start": 76,
                "end": 126,
            },
            {
                "source_extraction_id": "ext-11",
                "source_locator": "page:39:block:11",
                "start": 127,
                "end": 140,
            },
        ],
    }
    assert projected[0]["canonical_extractions"] == canonical
    assert [entry["status"] for entry in coverage] == [
        "incorporated",
        "incorporated",
        "incorporated",
    ]
    assert _compact_whitespace(projected[0]["text"]) == _compact_whitespace(
        "".join(str(item["raw_text"]) for item in canonical)
    )


def test_prose_continuation_avoids_extra_space_after_hyphen() -> None:
    canonical = [
        _extraction("ext-a", 7, 1, "This protects inter-"),
        _extraction("ext-b", 7, 3, "pretation from dehyphenation."),
    ]

    projected = project_reader_extractions(canonical)

    assert len(projected) == 1
    assert projected[0]["text"] == "This protects inter-pretation from dehyphenation."
    assert "interpretation" not in projected[0]["text"]


@pytest.mark.parametrize(
    ("previous", "following"),
    [
        (
            _extraction("a", 8, 1, "The room went quiet."),
            _extraction("b", 8, 2, "Vale stood."),
        ),
        (
            _extraction("a", 8, 1, "CHAPTER 12"),
            _extraction("b", 8, 2, "the room went quiet."),
        ),
        (
            _extraction("a", 8, 1, "The Platform"),
            _extraction("b", 8, 2, "the room went quiet."),
        ),
        (
            _extraction("a", 8, 1, "The thought continued"),
            _extraction("b", 9, 2, "across another page."),
        ),
    ],
)
def test_prose_continuation_does_not_cross_new_paragraph_heading_or_page_boundary(
    previous: dict[str, object],
    following: dict[str, object],
) -> None:
    projected = project_reader_extractions([previous, following])

    assert len(projected) == 2
    assert [item["source_extraction_id"] for item in projected] == [
        previous["id"],
        following["id"],
    ]
    assert all(item["reader_projection"] is None for item in projected)


def test_reader_projection_coverage_detects_dropped_extractions() -> None:
    canonical = [
        _extraction("ext-heading", 39, 1, "CHAPTER 12\n"),
        _extraction("ext-title", 39, 2, "The Platform\n"),
    ]
    projected = [
        {
            "region": "block:1",
            "text": "CHAPTER 12\n",
            "source_locator": "page:39:block:1",
            "source_extraction_id": "ext-heading",
            "reader_projection": None,
        }
    ]

    with pytest.raises(ReaderProjectionCoverageError, match="lost source extraction"):
        reader_projection_coverage(canonical, projected)


def test_reader_projection_coverage_detects_unknown_and_duplicate_sources() -> None:
    canonical = [_extraction("ext-a", 1, 1, "Alpha")]
    unknown = [{
        "region": "block:1",
        "text": "Alpha",
        "source_locator": "page:1:block:1",
        "reader_projection": {
            "kind": "soft_wrap_normalization",
            "source_extraction_ids": ["ext-missing"],
            "source_locators": ["page:1:block:1"],
        },
    }]
    duplicate = [
        {
            "region": "block:1",
            "text": "Alpha",
            "source_locator": "page:1:block:1",
            "source_extraction_id": "ext-a",
            "reader_projection": None,
        },
        {
            "region": "block:1",
            "text": "Alpha",
            "source_locator": "page:1:block:1",
            "reader_projection": {
                "kind": "soft_wrap_normalization",
                "source_extraction_ids": ["ext-a"],
                "source_locators": ["page:1:block:1"],
            },
        },
    ]

    with pytest.raises(ReaderProjectionCoverageError, match="unknown extraction"):
        reader_projection_coverage(canonical, unknown)
    with pytest.raises(ReaderProjectionCoverageError, match="accounted more than once"):
        reader_projection_coverage(canonical, duplicate)


def test_reader_api_projects_drop_cap_without_mutating_evidence(tmp_path: Path) -> None:
    db_path = tmp_path / "reader_projection.db"
    store = SQLiteStore(db_path)
    store.close()
    now = datetime.now(timezone.utc).isoformat()
    doc_id = "a" * 64
    continuation = "n my younger and more vulnerable years my father gave me some advice..."

    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 3, now, "test", "primary", 0),
    )
    for extraction in (
        _extraction("ext-I", 3, 2, "I\n"),
        _extraction("ext-rest", 3, 3, continuation + "\n"),
    ):
        conn.execute(
            """INSERT INTO source_extractions
               (id, document_id, page, region, raw_text, parser, parser_version,
                coordinates, source_locator, source_hash, hash, extracted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                extraction["id"],
                doc_id,
                extraction["page"],
                extraction["region"],
                extraction["raw_text"],
                "pymupdf",
                "test",
                "{}",
                extraction["source_locator"],
                doc_id,
                extraction["id"],
                now,
            ),
        )
    conn.execute(
        """INSERT INTO observations
           (id, source_document_id, source_extraction_id, raw_text,
            source_locator, semantic_hash, page, paragraph, sentence, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            "obs-rest",
            doc_id,
            "ext-rest",
            continuation,
            "page:3:block:3:sentence:1",
            "semantic",
            3,
            1,
            1,
            now,
        ),
    )
    conn.commit()
    conn.close()

    response = create_app(db_path=db_path).test_client().get(
        f"/api/reader/documents/{doc_id}/pages"
    )

    assert response.status_code == 200
    display_blocks = response.get_json()["pages"][0]["extractions"]
    coverage = response.get_json()["pages"][0]["projection_coverage"]
    assert len(display_blocks) == 1
    assert display_blocks[0]["text"] == "I" + continuation + "\n"
    assert display_blocks[0]["reader_projection"]["kind"] == "drop_cap_merge"
    assert [entry["source_extraction_id"] for entry in coverage] == [
        "ext-I",
        "ext-rest",
    ]
    assert {entry["status"] for entry in coverage} == {"incorporated"}

    verify = sqlite3.connect(db_path)
    canonical_extractions = verify.execute(
        """SELECT id, raw_text FROM source_extractions
           ORDER BY CAST(substr(region, 7) AS INTEGER)"""
    ).fetchall()
    canonical_observation = verify.execute(
        "SELECT source_extraction_id, raw_text FROM observations WHERE id = 'obs-rest'"
    ).fetchone()
    verify.close()

    assert canonical_extractions == [
        ("ext-I", "I\n"),
        ("ext-rest", continuation + "\n"),
    ]
    assert canonical_observation == ("ext-rest", continuation)


def test_reader_api_projects_prose_continuation_without_mutating_evidence(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "reader_projection_prose.db"
    store = SQLiteStore(db_path)
    store.close()
    now = datetime.now(timezone.utc).isoformat()
    doc_id = "c" * 64
    blocks = [
        (8, "The first line of the manuscript had not yet "),
        (10, "become readable in the Reader projection."),
    ]

    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "second-sale.pdf", doc_id, 39, now, "test", "primary", 0),
    )
    for block, raw_text in blocks:
        extraction_id = f"ext-{block:02d}"
        conn.execute(
            """INSERT INTO source_extractions
               (id, document_id, page, region, raw_text, parser, parser_version,
                coordinates, source_locator, source_hash, hash, extracted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                extraction_id,
                doc_id,
                39,
                f"block:{block}",
                raw_text,
                "pymupdf",
                "test",
                "{}",
                f"page:39:block:{block}",
                doc_id,
                extraction_id,
                now,
            ),
        )
    conn.execute(
        """INSERT INTO observations
           (id, source_document_id, source_extraction_id, raw_text,
            source_locator, semantic_hash, page, paragraph, sentence, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            "obs-08",
            doc_id,
            "ext-08",
            blocks[0][1],
            "page:39:block:8:sentence:1",
            "semantic-08",
            39,
            1,
            1,
            now,
        ),
    )
    conn.commit()
    conn.close()

    response = create_app(db_path=db_path).test_client().get(
        f"/api/reader/documents/{doc_id}/pages"
    )

    assert response.status_code == 200
    page = response.get_json()["pages"][0]
    assert len(page["extractions"]) == 1
    assert page["extractions"][0]["text"] == (
        "The first line of the manuscript had not yet "
        "become readable in the Reader projection."
    )
    assert page["extractions"][0]["reader_projection"]["kind"] == (
        "prose_continuation_merge"
    )
    assert [entry["status"] for entry in page["projection_coverage"]] == [
        "incorporated",
        "incorporated",
    ]

    verify = sqlite3.connect(db_path)
    canonical_extractions = verify.execute(
        """SELECT id, raw_text FROM source_extractions
           ORDER BY CAST(substr(region, 7) AS INTEGER)"""
    ).fetchall()
    canonical_observation = verify.execute(
        "SELECT source_extraction_id, raw_text FROM observations WHERE id = 'obs-08'"
    ).fetchone()
    verify.close()

    assert canonical_extractions == [
        ("ext-08", blocks[0][1]),
        ("ext-10", blocks[1][1]),
    ]
    assert canonical_observation == ("ext-08", blocks[0][1])


def test_reader_api_orders_blocks_numerically_and_accounts_for_chapter_page(
    tmp_path: Path,
) -> None:
    """Regression for issue #123: source_locator text order put block:10 before
    block:2, making intervening manuscript prose look absent in the Reader.
    """
    db_path = tmp_path / "reader_projection_order.db"
    store = SQLiteStore(db_path)
    store.close()
    now = datetime.now(timezone.utc).isoformat()
    doc_id = "b" * 64
    blocks = [
        (1, "39THE SECOND SALE\n\nCHAPTER 12\n"),
        (2, "The Platform\n"),
        (3, "Vale's agency held the platform meeting in a room with no books.\n"),
        (
            4,
            "The walls displayed photographs of clients on stages, television sets, "
            "conference screens, university lecterns, and magazine covers. A monitor "
            "showed a dashboard titled POST-PUBLICATION CONVERSION PLAN.\n",
        ),
        (
            8,
            "Elias attended because Harbor & Quill needed to coordinate direct sales, "
            "signed stock, donor messages, and the author's media calendar. Derek sat "
            "beside Vale's agent, Martin Saye, who wore the satisfied expression of a "
            "person whose client had not yet ",
        ),
        (10, "become a bestseller but had already begun charging as if he had.\n"),
        (11, "Saye advanced the first slide.\n"),
    ]

    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "the-second-sale.pdf", doc_id, 39, now, "test", "primary", 0),
    )
    for block, raw_text in blocks:
        extraction_id = f"ext-{block:02d}"
        conn.execute(
            """INSERT INTO source_extractions
               (id, document_id, page, region, raw_text, parser, parser_version,
                coordinates, source_locator, source_hash, hash, extracted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                extraction_id,
                doc_id,
                39,
                f"block:{block}",
                raw_text,
                "pymupdf",
                "test",
                "{}",
                f"page:39:block:{block}",
                doc_id,
                extraction_id,
                now,
            ),
        )
    conn.commit()
    conn.close()

    response = create_app(db_path=db_path).test_client().get(
        f"/api/reader/documents/{doc_id}/pages"
    )

    assert response.status_code == 200
    page = response.get_json()["pages"][0]
    rendered_text = "".join(block["text"] for block in page["extractions"])
    assert rendered_text.index("CHAPTER 12") < rendered_text.index("The Platform")
    assert rendered_text.index("The Platform") < rendered_text.index("Vale's agency")
    assert rendered_text.index("Vale's agency") < rendered_text.index("The walls displayed")
    assert rendered_text.index("had not yet") < rendered_text.index("become a bestseller")
    assert rendered_text.index("become a bestseller") < rendered_text.index(
        "Saye advanced the first slide"
    )

    expected_ids = [f"ext-{block:02d}" for block, _ in blocks]
    assert [
        block["reader_projection"]["source_extraction_ids"][0]
        for block in page["extractions"][:4]
    ] == expected_ids[:4]
    merged = page["extractions"][4]
    assert merged["reader_projection"]["kind"] == "prose_continuation_merge"
    assert merged["reader_projection"]["source_extraction_ids"] == ["ext-08", "ext-10"]
    assert page["extractions"][5]["reader_projection"]["source_extraction_ids"] == [
        "ext-11"
    ]
    assert [
        entry["source_extraction_id"] for entry in page["projection_coverage"]
    ] == expected_ids
    assert {entry["status"] for entry in page["projection_coverage"]} == {
        "incorporated"
    }
