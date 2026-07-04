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
from hermeneia.web.reader_projection import project_reader_extractions


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
    }
    assert projected[0]["canonical_extractions"] == canonical


@pytest.mark.parametrize(
    ("previous", "following"),
    [
        (_extraction("a", 3, 2, "I.\n"), _extraction("b", 3, 3, "n continuation")),
        (_extraction("a", 3, 2, "I\n"), _extraction("b", 3, 3, "Next paragraph")),
        (_extraction("a", 3, 2, "I\n"), _extraction("b", 4, 3, "n next page")),
        (_extraction("a", 3, 2, "I\n"), _extraction("b", 3, 4, "n nonadjacent")),
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
    assert len(display_blocks) == 1
    assert display_blocks[0]["text"] == "I" + continuation + "\n"
    assert display_blocks[0]["reader_projection"]["kind"] == "drop_cap_merge"

    verify = sqlite3.connect(db_path)
    canonical_extractions = verify.execute(
        "SELECT id, raw_text FROM source_extractions ORDER BY source_locator"
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
