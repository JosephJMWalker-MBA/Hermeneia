"""Derived authored-structure inference for Reader evidence."""
from __future__ import annotations

import copy
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.workspace import export_workspace_bundle, restore_workspace
from hermeneia.web.app import create_app
from hermeneia.web.reader_structure import (
    STRUCTURE_INFERENCE_VERSION,
    candidate_snapshot,
    infer_reader_structure,
)
from hermeneia.web.reader_structure_stewardship import decision_row


def _extraction(
    extraction_id: str,
    page: int,
    block: int,
    raw_text: str,
    doc_id: str = "doc-structure",
) -> dict[str, object]:
    return {
        "id": extraction_id,
        "document_id": doc_id,
        "page": page,
        "region": f"block:{block}",
        "raw_text": raw_text,
        "coordinates": json.dumps(
            {"x0": 72.0, "y0": float(block * 24), "x1": 540.0, "y1": float(block * 24 + 16)},
            sort_keys=True,
            separators=(",", ":"),
        ),
        "source_locator": f"page:{page}:block:{block}",
    }


def _items(extractions: list[dict[str, object]], doc_id: str = "doc-structure") -> list[dict[str, object]]:
    return infer_reader_structure(doc_id, extractions)["items"]


def _second_sale_sequence(doc_id: str = "doc-structure") -> list[dict[str, object]]:
    return [
        _extraction("ext-c12", 41, 1, "CHAPTER 12\n", doc_id),
        _extraction("ext-t12", 41, 2, "The First Sale\n", doc_id),
        _extraction(
            "ext-p12",
            41,
            3,
            "Saye closed the presentation before the donor questions began.\n",
            doc_id,
        ),
        _extraction("ext-c13", 42, 1, "CHAPTER 13\n", doc_id),
        _extraction("ext-t13", 42, 2, "The Donor Room\n", doc_id),
        _extraction(
            "ext-p13",
            42,
            3,
            "Meridian Civic Group held its launch reception in a bright donor room.\n",
            doc_id,
        ),
    ]


def _seed_structure_workspace(tmp_path: Path) -> tuple[Path, str, list[dict[str, object]]]:
    db_path = tmp_path / "reader_structure.db"
    SQLiteStore(db_path).close()
    now = datetime.now(timezone.utc).isoformat()
    doc_id = "s" * 64
    rows = _second_sale_sequence(doc_id)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "the-second-sale.pdf", doc_id, 42, now, "test", "primary", 0),
    )
    for row in rows:
        conn.execute(
            """INSERT INTO source_extractions
               (id, document_id, page, region, raw_text, parser, parser_version,
                coordinates, source_locator, source_hash, hash, extracted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["id"],
                doc_id,
                row["page"],
                row["region"],
                row["raw_text"],
                "pymupdf",
                "test",
                row["coordinates"],
                row["source_locator"],
                doc_id,
                row["id"],
                now,
            ),
        )
    conn.commit()
    conn.close()
    return db_path, doc_id, rows


def _insert_structure_decision(
    db_path: Path,
    candidate: dict[str, object],
    *,
    verdict: str = "accepted",
    rationale: str = "Confirmed by steward.",
    decided_at: str = "2026-07-01T00:00:00+00:00",
    supersedes_decision_id: str | None = None,
) -> dict[str, object]:
    row = decision_row(
        candidate=candidate,
        candidate_snapshot=candidate_snapshot(candidate),
        verdict=verdict,
        rationale=rationale,
        steward_id="test-steward",
        decided_at=decided_at,
        supersedes_decision_id=supersedes_decision_id,
    )
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO reader_structure_decisions
           (id, candidate_id, document_id, candidate_snapshot,
            candidate_inference_version, verdict, rationale, steward_id,
            decided_at, supersedes_decision_id, created_at)
           VALUES (:id, :candidate_id, :document_id, :candidate_snapshot,
                   :candidate_inference_version, :verdict, :rationale,
                   :steward_id, :decided_at, :supersedes_decision_id,
                   :created_at)""",
        row,
    )
    conn.commit()
    conn.close()
    return row


def _source_rows(db_path: Path) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            """SELECT id, document_id, page, region, raw_text, coordinates,
                      source_locator
                 FROM source_extractions
                ORDER BY page, region, id"""
        ).fetchall()
    finally:
        conn.close()


def test_second_sale_sequence_inflects_strong_chapter_start_with_provenance() -> None:
    rows = [
        _extraction("ext-prose-1", 41, 8, "Saye closed the presentation.\n"),
        _extraction("ext-prose-2", 41, 9, '"When the next reason is ready," he said.\n'),
        _extraction("ext-header", 42, 1, "42THE SECOND SALE\n"),
        _extraction("ext-heading", 42, 2, "CHAPTER 13\n"),
        _extraction("ext-title", 42, 3, "The Donor Room\n"),
        _extraction(
            "ext-resume",
            42,
            4,
            "Meridian Civic Group held its launch reception in a bright donor room.\n",
        ),
    ]
    before = copy.deepcopy(rows)

    items = _items(rows)

    assert rows == before, "structure inference must not mutate source extraction rows"
    assert len(items) == 1
    chapter = items[0]
    assert chapter["kind"] == "chapter"
    assert chapter["heading_text"] == "CHAPTER 13"
    assert chapter["title_text"] == "The Donor Room"
    assert chapter["confidence"] == "high"
    assert {
        "heading_shape",
        "isolated_heading_block",
        "adjacent_title_block",
        "prose_resumes_after",
        "preceding_prose_context",
        "page_transition_context",
        "probable_running_header",
    } <= set(chapter["basis"])
    assert chapter["start_locator"] == "page:42:block:2"
    assert chapter["start_context_locator"] == "page:42:block:1"
    assert chapter["status"] == "derived"
    assert chapter["start_status"] == "inferred_from_source_evidence"
    assert chapter["contributing_extraction_ids"] == [
        "ext-prose-2",
        "ext-header",
        "ext-heading",
        "ext-title",
        "ext-resume",
    ]
    evidence = {block["role"]: block for block in chapter["evidence_blocks"]}
    assert evidence["probable_running_header"]["raw_text"] == "42THE SECOND SALE\n"
    assert evidence["heading"]["raw_text"] == "CHAPTER 13\n"
    assert evidence["title"]["source_locator"] == "page:42:block:3"


def test_prose_mention_of_chapter_number_is_not_a_boundary() -> None:
    rows = [
        _extraction(
            "ext-prose",
            7,
            3,
            "In chapter 13 of the report, Elias found the donor figures.\n",
        )
    ]

    assert _items(rows) == []


def test_isolated_heading_keyword_alone_stays_low_confidence_candidate() -> None:
    rows = [_extraction("ext-heading", 13, 1, "CHAPTER 13\n")]

    items = _items(rows)

    assert len(items) == 1
    assert items[0]["kind"] == "chapter"
    assert items[0]["confidence"] == "candidate"
    assert "heading_shape" in items[0]["basis"]
    assert "prose_resumes_after" not in items[0]["basis"]
    assert items[0]["end_status"] == "open"


def test_repeated_chapter_pattern_stabilizes_confidence_and_infers_ends() -> None:
    rows = [
        _extraction("ext-c1", 1, 1, "CHAPTER 1\n"),
        _extraction("ext-t1", 1, 2, "Opening Night\n"),
        _extraction("ext-p1", 1, 3, "The first reception began before the donors arrived.\n"),
        _extraction("ext-c2", 2, 1, "CHAPTER 2\n"),
        _extraction("ext-t2", 2, 2, "The Ledger\n"),
        _extraction("ext-p2", 2, 3, "The ledger carried names that no one said aloud.\n"),
        _extraction("ext-c3", 3, 1, "CHAPTER 3\n"),
        _extraction("ext-t3", 3, 2, "After the Launch\n"),
        _extraction("ext-p3", 3, 3, "After the launch, Elias counted the empty seats again.\n"),
    ]

    chapters = _items(rows)

    assert [item["heading_text"] for item in chapters] == [
        "CHAPTER 1",
        "CHAPTER 2",
        "CHAPTER 3",
    ]
    assert {item["confidence"] for item in chapters} == {"high"}
    assert all("repeated_document_pattern" in item["basis"] for item in chapters)
    assert all("coherent_sequence" in item["basis"] for item in chapters)
    assert chapters[0]["end_locator"] == "page:1:block:3"
    assert chapters[0]["end_status"] == "derived_from_next_structure_start"
    assert chapters[0]["end_contributing_extraction_id"] == "ext-p1"
    assert chapters[1]["end_locator"] == "page:2:block:3"
    assert chapters[2]["end_status"] == "open"


def test_non_chapter_part_convention_is_detected_without_chapter_keyword() -> None:
    rows = [
        _extraction("ext-part-i", 1, 1, "PART I\n"),
        _extraction("ext-title-i", 1, 2, "Autumn\n"),
        _extraction("ext-prose-i", 1, 3, "Autumn left the campaign office colder than expected.\n"),
        _extraction("ext-part-ii", 9, 1, "PART II\n"),
        _extraction("ext-title-ii", 9, 2, "Winter\n"),
        _extraction("ext-prose-ii", 9, 3, "Winter made the donor room feel newly ceremonial.\n"),
    ]

    parts = _items(rows)

    assert [item["kind"] for item in parts] == ["part", "part"]
    assert [item["heading_text"] for item in parts] == ["PART I", "PART II"]
    assert parts[1]["title_text"] == "Winter"
    assert {item["confidence"] for item in parts} == {"high"}
    assert all("repeated_document_pattern" in item["basis"] for item in parts)


def test_page_numbers_and_publication_footers_do_not_become_sections() -> None:
    rows = [
        _extraction("ext-page-10", 10, 0, "10\n"),
        _extraction("ext-footer-10", 10, 1, "Free eBooks at Planet eBook.com\n"),
        _extraction(
            "ext-prose-10",
            10,
            2,
            "He stretched out his arms toward the dark water in a curious way.\n",
        ),
        _extraction("ext-page-11", 11, 0, "11\n"),
        _extraction("ext-footer-11", 11, 1, "Free eBooks at Planet eBook.com\n"),
        _extraction(
            "ext-prose-11",
            11,
            2,
            "I glanced seaward and distinguished nothing except a single green light.\n",
        ),
    ]

    assert _items(rows) == []


def test_drop_cap_after_chapter_heading_is_not_a_title_signal() -> None:
    rows = [
        _extraction("ext-heading", 26, 1, "Chapter 2\n"),
        _extraction("ext-drop-cap", 26, 2, "A\n"),
        _extraction(
            "ext-continuation",
            26,
            3,
            "bout half way between West Egg and New York the motor road joins the railroad.\n",
        ),
    ]

    items = _items(rows)

    assert len(items) == 1
    assert items[0]["confidence"] == "candidate"
    assert items[0]["title_text"] is None
    assert "adjacent_title_block" not in items[0]["basis"]


def test_output_is_deterministic_over_identical_evidence() -> None:
    rows = [
        _extraction("ext-c1", 1, 1, "CHAPTER 1\n"),
        _extraction("ext-t1", 1, 2, "Opening Night\n"),
        _extraction("ext-p1", 1, 3, "The first reception began before the donors arrived.\n"),
        _extraction("ext-c2", 2, 1, "CHAPTER 2\n"),
        _extraction("ext-t2", 2, 2, "The Ledger\n"),
        _extraction("ext-p2", 2, 3, "The ledger carried names that no one said aloud.\n"),
    ]

    assert infer_reader_structure("doc-structure", rows) == infer_reader_structure(
        "doc-structure", copy.deepcopy(rows)
    )


def test_candidate_identity_tracks_evidence_and_inference_version() -> None:
    rows = _second_sale_sequence()

    original = _items(rows)[0]
    identical = _items(copy.deepcopy(rows))[0]
    material_change = copy.deepcopy(rows)
    material_change[2]["raw_text"] = (
        "Saye ended the presentation after the donor questions began.\n"
    )
    changed = _items(material_change)[0]
    next_version = infer_reader_structure(
        "doc-structure",
        rows,
        inference_version="reader-structure@2",
    )["items"][0]

    assert original["candidate_id"] == original["id"]
    assert original["candidate_id"] == identical["candidate_id"]
    assert original["candidate_id"] != changed["candidate_id"]
    assert original["candidate_id"] != next_version["candidate_id"]
    assert original["inference_version"] == STRUCTURE_INFERENCE_VERSION
    assert original["evidence_fingerprint"] != changed["evidence_fingerprint"]


def test_reader_structure_api_is_read_only_and_inspectable(tmp_path: Path) -> None:
    db_path = tmp_path / "reader_structure.db"
    store = SQLiteStore(db_path)
    store.close()
    now = datetime.now(timezone.utc).isoformat()
    doc_id = "s" * 64
    rows = [
        _extraction("ext-prose-1", 41, 8, "Saye closed the presentation.\n", doc_id),
        _extraction("ext-prose-2", 41, 9, '"When the next reason is ready," he said.\n', doc_id),
        _extraction("ext-header", 42, 1, "42THE SECOND SALE\n", doc_id),
        _extraction("ext-heading", 42, 2, "CHAPTER 13\n", doc_id),
        _extraction("ext-title", 42, 3, "The Donor Room\n", doc_id),
        _extraction(
            "ext-resume",
            42,
            4,
            "Meridian Civic Group held its launch reception in a bright donor room.\n",
            doc_id,
        ),
    ]

    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "the-second-sale.pdf", doc_id, 42, now, "test", "primary", 0),
    )
    for row in rows:
        conn.execute(
            """INSERT INTO source_extractions
               (id, document_id, page, region, raw_text, parser, parser_version,
                coordinates, source_locator, source_hash, hash, extracted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["id"],
                doc_id,
                row["page"],
                row["region"],
                row["raw_text"],
                "pymupdf",
                "test",
                row["coordinates"],
                row["source_locator"],
                doc_id,
                row["id"],
                now,
            ),
        )
    conn.commit()
    before_rows = conn.execute(
        "SELECT id, raw_text FROM source_extractions ORDER BY page, region, id"
    ).fetchall()
    before_highlights = conn.execute("SELECT COUNT(*) FROM reader_highlights").fetchone()[0]
    before_log = conn.execute("SELECT COUNT(*) FROM investigation_log").fetchone()[0]
    before_decisions = conn.execute(
        "SELECT COUNT(*) FROM reader_structure_decisions"
    ).fetchone()[0]
    conn.close()

    client = create_app(db_path=db_path).test_client()
    pages_response = client.get(f"/api/reader/documents/{doc_id}/pages")
    structure_response = client.get(f"/api/reader/documents/{doc_id}/structure")

    assert pages_response.status_code == 200
    assert structure_response.status_code == 200
    payload = structure_response.get_json()
    structure = payload["structure"]
    assert structure["storage"] == "computed_on_demand"
    assert structure["evidence_available"]["block_coordinates"] is True
    assert structure["evidence_available"]["font_metadata"] is False
    assert structure["items"][0]["heading_text"] == "CHAPTER 13"
    assert structure["items"][0]["title_text"] == "The Donor Room"
    assert structure["items"][0]["confidence"] == "high"
    assert structure["items"][0]["stewardship"]["status"] == "undecided"
    assert structure["items"][0]["stewardship"]["history"] == []
    assert structure["accepted_structure"] == []
    assert "probable_running_header" in structure["items"][0]["basis"]
    assert "ext-header" in structure["items"][0]["contributing_extraction_ids"]

    verify = sqlite3.connect(db_path)
    after_rows = verify.execute(
        "SELECT id, raw_text FROM source_extractions ORDER BY page, region, id"
    ).fetchall()
    after_highlights = verify.execute("SELECT COUNT(*) FROM reader_highlights").fetchone()[0]
    after_log = verify.execute("SELECT COUNT(*) FROM investigation_log").fetchone()[0]
    after_decisions = verify.execute(
        "SELECT COUNT(*) FROM reader_structure_decisions"
    ).fetchone()[0]
    verify.close()

    assert after_rows == before_rows
    assert after_highlights == before_highlights
    assert after_log == before_log
    assert after_decisions == before_decisions == 0


def test_reader_structure_decisions_append_and_resolve_effective_status(
    tmp_path: Path,
) -> None:
    db_path, doc_id, _rows = _seed_structure_workspace(tmp_path)
    before_source = _source_rows(db_path)
    conn = sqlite3.connect(db_path)
    before_highlights = conn.execute("SELECT COUNT(*) FROM reader_highlights").fetchone()[0]
    before_log = conn.execute("SELECT COUNT(*) FROM investigation_log").fetchone()[0]
    conn.close()

    client = create_app(db_path=db_path).test_client()
    initial = client.get(f"/api/reader/documents/{doc_id}/structure").get_json()
    candidates = initial["structure"]["items"]
    assert len(candidates) == 2
    assert {item["confidence"] for item in candidates} == {"high"}
    assert {item["stewardship"]["status"] for item in candidates} == {"undecided"}

    first = candidates[0]
    second = candidates[1]
    accept = client.post(
        f"/api/reader/structure/{first['candidate_id']}/decisions",
        json={
            "document_id": doc_id,
            "verdict": "accepted",
            "rationale": "Chapter boundary confirmed by the steward.",
            "steward_id": "joseph",
        },
    )
    assert accept.status_code == 201
    accepted_decision = accept.get_json()["decision"]
    assert accept.get_json()["candidate"]["stewardship"]["status"] == "accepted"

    reject = client.post(
        f"/api/reader/structure/{second['candidate_id']}/decisions",
        json={
            "document_id": doc_id,
            "verdict": "rejected",
            "rationale": "The sequence is visible but not accepted for this study.",
            "steward_id": "joseph",
        },
    )
    assert reject.status_code == 201
    assert reject.get_json()["candidate"]["stewardship"]["status"] == "rejected"

    superseding = client.post(
        f"/api/reader/structure/{first['candidate_id']}/decisions",
        json={
            "document_id": doc_id,
            "verdict": "rejected",
            "rationale": "Reconsidered after reviewing the preceding page.",
            "steward_id": "joseph",
        },
    )
    assert superseding.status_code == 201
    superseding_decision = superseding.get_json()["decision"]
    assert superseding_decision["supersedes_decision_id"] == accepted_decision["decision_id"]

    reloaded = client.get(f"/api/reader/documents/{doc_id}/structure").get_json()
    by_id = {
        item["candidate_id"]: item
        for item in reloaded["structure"]["items"]
    }
    first_stewardship = by_id[first["candidate_id"]]["stewardship"]
    assert first_stewardship["status"] == "rejected"
    assert first_stewardship["effective_decision"]["rationale"] == (
        "Reconsidered after reviewing the preceding page."
    )
    assert len(first_stewardship["history"]) == 2
    assert first_stewardship["history"][0]["superseded"] is True
    assert first_stewardship["history"][1]["superseded"] is False
    assert len(reloaded["structure"]["rejected_candidates"]) == 2
    assert reloaded["structure"]["accepted_structure"] == []

    verify = sqlite3.connect(db_path)
    try:
        after_highlights = verify.execute(
            "SELECT COUNT(*) FROM reader_highlights"
        ).fetchone()[0]
        after_log = verify.execute("SELECT COUNT(*) FROM investigation_log").fetchone()[0]
        assert after_highlights == before_highlights
        assert after_log == before_log
    finally:
        verify.close()
    assert _source_rows(db_path) == before_source

    immutable = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            immutable.execute(
                "UPDATE reader_structure_decisions SET verdict = 'accepted' WHERE id = ?",
                (superseding_decision["decision_id"],),
            )
        immutable.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            immutable.execute(
                "DELETE FROM reader_structure_decisions WHERE id = ?",
                (superseding_decision["decision_id"],),
            )
    finally:
        immutable.close()


def test_prior_inference_version_decision_does_not_bind_to_current_candidate(
    tmp_path: Path,
) -> None:
    db_path, doc_id, rows = _seed_structure_workspace(tmp_path)
    old_candidate = infer_reader_structure(
        doc_id,
        rows,
        inference_version="reader-structure@previous",
    )["items"][0]
    _insert_structure_decision(db_path, old_candidate)

    client = create_app(db_path=db_path).test_client()
    payload = client.get(f"/api/reader/documents/{doc_id}/structure").get_json()
    current = payload["structure"]["items"][0]

    assert current["candidate_id"] != old_candidate["candidate_id"]
    assert current["stewardship"]["status"] == "undecided"
    assert current["stewardship"]["history"] == []
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM reader_structure_decisions"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_reader_structure_decisions_round_trip_through_wbs(tmp_path: Path) -> None:
    db_path, doc_id, _rows = _seed_structure_workspace(tmp_path)
    client = create_app(db_path=db_path).test_client()
    initial = client.get(f"/api/reader/documents/{doc_id}/structure").get_json()
    target = initial["structure"]["items"][0]
    rejected_target = initial["structure"]["items"][1]
    response = client.post(
        f"/api/reader/structure/{target['candidate_id']}/decisions",
        json={
            "document_id": doc_id,
            "verdict": "accepted",
            "rationale": "Second Sale chapter boundary accepted.",
            "steward_id": "joseph",
        },
    )
    assert response.status_code == 201
    reject_response = client.post(
        f"/api/reader/structure/{rejected_target['candidate_id']}/decisions",
        json={
            "document_id": doc_id,
            "verdict": "rejected",
            "rationale": "Second Sale adjacent candidate rejected.",
            "steward_id": "joseph",
        },
    )
    assert reject_response.status_code == 201

    bundle = tmp_path / "bundle"
    manifest = export_workspace_bundle(
        db_path,
        bundle,
        generated_at="2026-07-04T15:00:00+00:00",
        workspace_id="second-sale",
    )
    governance_file = bundle / "governance" / "reader_structure_decisions.json"
    assert governance_file.is_file()
    assert manifest["wbs_version"] == "1.0"
    assert manifest["counts"]["reader_structure_decisions"] == 2
    roles = {entry["path"]: entry["role"] for entry in manifest["files"]}
    assert roles["governance/reader_structure_decisions.json"] == "authored"

    restored_db = tmp_path / "restored" / "workspace.db"
    restored_db.parent.mkdir(parents=True)
    result = restore_workspace(restored_db, bundle)
    assert result["restored"]["reader_structure_decisions"] == 2

    restored_client = create_app(db_path=restored_db).test_client()
    restored = restored_client.get(f"/api/reader/documents/{doc_id}/structure").get_json()
    restored_by_id = {
        item["candidate_id"]: item
        for item in restored["structure"]["items"]
    }
    restored_target = restored_by_id[target["candidate_id"]]
    restored_rejected = restored_by_id[rejected_target["candidate_id"]]
    assert restored_target["candidate_id"] == target["candidate_id"]
    assert restored_target["stewardship"]["status"] == "accepted"
    assert restored_target["stewardship"]["effective_decision"]["rationale"] == (
        "Second Sale chapter boundary accepted."
    )
    assert restored_rejected["stewardship"]["status"] == "rejected"
    assert restored_rejected in restored["structure"]["rejected_candidates"]

    reexported = tmp_path / "reexported"
    export_workspace_bundle(
        restored_db,
        reexported,
        generated_at="2026-07-04T15:00:00+00:00",
        workspace_id="second-sale",
    )
    assert governance_file.read_bytes() == (
        reexported / "governance" / "reader_structure_decisions.json"
    ).read_bytes()
