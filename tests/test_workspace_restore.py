"""Workspace Bundle restore + round-trip conformance (WBS v1, §5.2).

Restore reconstitutes a fresh workspace from a bundle. The round-trip test is
the spec's core guarantee: seed a DB → export → restore into a fresh DB → the
canonical and authored records are identical. Derived data is regenerated, not
asserted byte-for-byte.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.reader_structure import (
    make_structure_candidate_id,
    structure_evidence_fingerprint,
)
from hermeneia.web.reader_structure_stewardship import (
    canonical_json,
    make_reader_structure_decision_id,
)
from hermeneia.workspace import (
    RestoreError,
    export_workspace_bundle,
    preview_restore,
    restore_workspace,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed(db_path: Path) -> str:
    SQLiteStore(db_path).close()
    doc_id = "a" * 64
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 3, _now(), "test-v1", "primary", 0),
    )
    conn.execute(
        """INSERT INTO source_extractions
           (id, document_id, page, region, raw_text, parser, parser_version,
            coordinates, source_locator, source_hash, hash, extracted_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("ext-1", doc_id, 2, "block:4", "the green light", "pymupdf", "1.7",
         "{}", "page:2:block:4", doc_id, "ext-1", _now()),
    )
    conn.execute(
        """INSERT INTO reader_highlights
           (id, source_document_id, source_role, page, source_locator,
            selected_text, note_text, question_text, relevance, tags, status,
            rank, theme_bucket, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("hl-1", doc_id, "primary", 2, "page:2:block:4", "the green light",
         "Aspiration.", "Does hope require distance?", "unclear", "[]",
         "saved_highlight", 5, "aspiration", _now(), _now()),
    )
    conn.execute(
        """INSERT INTO investigation_log
           (id, lane, understanding, pressing_questions, source_document_id,
            page, governing_question, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        ("fn-1", "corpus", "Distance sustains desire.", None, doc_id, 2,
         "How does desire depend on distance?", _now()),
    )
    conn.execute(
        """INSERT INTO workspace_investigation
           (id, thesis, purpose, lenses, reconsider, created_at, updated_at)
           VALUES ('current', ?, ?, ?, ?, ?, ?)""",
        ("How does desire depend on distance?", "Trace aspiration.",
         '["aspiration"]', None, "2026-07-01T00:00:00+00:00", _now()),
    )
    conn.commit()
    conn.close()

    uploads = db_path.parent / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    (uploads / "gatsby_x.pdf").write_bytes(b"%PDF-1.7 fake gatsby")
    return doc_id


def _export(db_path: Path, out: Path) -> None:
    export_workspace_bundle(
        db_path, out,
        generated_at="2026-07-04T15:00:00+00:00", workspace_id="ws",
    )


def _rowdicts(db_path: Path, sql: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def _reader_structure_decision(
    doc_id: str,
    *,
    rationale: str = "Historical structure boundary accepted.",
    supersedes_decision_id: str | None = None,
) -> dict:
    evidence_blocks = [
        {
            "role": "heading",
            "source_extraction_id": "ext-1",
            "page": 2,
            "region": "block:4",
            "source_locator": "page:2:block:4",
            "raw_text": "the green light",
        }
    ]
    fingerprint = structure_evidence_fingerprint(evidence_blocks)
    candidate_id = make_structure_candidate_id(
        document_id=doc_id,
        kind="chapter",
        source_locator="page:2:block:4",
        heading_text="the green light",
        title_text=None,
        contributing_ids=["ext-1"],
        contributing_locators=["page:2:block:4"],
        evidence_fingerprint=fingerprint,
        inference_version="reader-structure@1",
    )
    snapshot = {
        "candidate_id": candidate_id,
        "document_id": doc_id,
        "kind": "chapter",
        "heading_text": "the green light",
        "title_text": None,
        "start_page": 2,
        "start_locator": "page:2:block:4",
        "start_context_page": 2,
        "start_context_locator": "page:2:block:4",
        "start_status": "inferred_from_source_evidence",
        "end_page": None,
        "end_locator": None,
        "end_status": "open",
        "confidence": "candidate",
        "confidence_score": 1,
        "confidence_model": "deterministic additive basis count",
        "basis": ["heading_shape"],
        "contributing_extraction_ids": ["ext-1"],
        "contributing_locators": ["page:2:block:4"],
        "evidence_fingerprint": fingerprint,
        "evidence_blocks": evidence_blocks,
        "status": "derived",
        "inference_version": "reader-structure@1",
    }
    decided_at = "2026-07-01T00:00:00+00:00"
    decision_id = make_reader_structure_decision_id(
        candidate_id=candidate_id,
        verdict="accepted",
        rationale=rationale,
        steward_id="test-steward",
        decided_at=decided_at,
        supersedes_decision_id=supersedes_decision_id,
    )
    return {
        "id": decision_id,
        "candidate_id": candidate_id,
        "document_id": doc_id,
        "candidate_snapshot": canonical_json(snapshot),
        "candidate_inference_version": "reader-structure@1",
        "verdict": "accepted",
        "rationale": rationale,
        "steward_id": "test-steward",
        "decided_at": decided_at,
        "supersedes_decision_id": supersedes_decision_id,
        "created_at": decided_at,
    }


def _insert_reader_structure_decision(db_path: Path, doc_id: str) -> dict:
    row = _reader_structure_decision(doc_id)
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


# ── Round-trip conformance ─────────────────────────────────────────────────


def test_round_trip_preserves_canonical_and_authored(tmp_path: Path):
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    _seed(src)
    bundle = tmp_path / "bundle"
    _export(src, bundle)

    dst = tmp_path / "dst" / "workspace.db"
    dst.parent.mkdir(parents=True)
    result = restore_workspace(dst, bundle)
    assert result["restored"]["source_documents"] == 1
    assert result["restored"]["reader_highlights"] == 1

    for sql in (
        "SELECT * FROM source_documents",
        "SELECT * FROM source_extractions",
        "SELECT * FROM reader_highlights ORDER BY id",
        "SELECT * FROM investigation_log ORDER BY id",
        "SELECT thesis, purpose, lenses, reconsider, created_at FROM workspace_investigation",
    ):
        assert _rowdicts(src, sql) == _rowdicts(dst, sql), sql


def test_round_trip_preserves_reader_structure_decisions(tmp_path: Path):
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    doc_id = _seed(src)
    _insert_reader_structure_decision(src, doc_id)
    bundle = tmp_path / "bundle"
    _export(src, bundle)

    dst = tmp_path / "dst" / "workspace.db"
    dst.parent.mkdir(parents=True)
    result = restore_workspace(dst, bundle)

    assert result["restored"]["reader_structure_decisions"] == 1
    assert _rowdicts(
        src,
        "SELECT * FROM reader_structure_decisions ORDER BY id",
    ) == _rowdicts(
        dst,
        "SELECT * FROM reader_structure_decisions ORDER BY id",
    )


def test_round_trip_preserves_uploads(tmp_path: Path):
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    _seed(src)
    bundle = tmp_path / "bundle"
    _export(src, bundle)
    dst = tmp_path / "dst" / "workspace.db"
    dst.parent.mkdir(parents=True)
    restore_workspace(dst, bundle)

    restored_uploads = list((dst.parent / "uploads").iterdir())
    assert len(restored_uploads) == 1
    assert restored_uploads[0].read_bytes() == b"%PDF-1.7 fake gatsby"


def test_restored_workspace_re_exports_identically(tmp_path: Path):
    """Export → restore → export produces identical canonical/authored files."""
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    _seed(src)
    b1 = tmp_path / "b1"
    _export(src, b1)
    dst = tmp_path / "dst" / "workspace.db"
    dst.parent.mkdir(parents=True)
    restore_workspace(dst, b1)
    b2 = tmp_path / "b2"
    _export(dst, b2)

    for rel in (
        "corpus/documents.json",
        "corpus/extractions.json",
        "governance/reader_structure_decisions.json",
        "study/highlights.json",
        "study/field_notes.json",
        "investigation.json",
    ):
        assert (b1 / rel).read_bytes() == (b2 / rel).read_bytes(), rel


# ── Preview + safety ───────────────────────────────────────────────────────


def test_preview_reports_what_would_be_created(tmp_path: Path):
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    _seed(src)
    bundle = tmp_path / "bundle"
    _export(src, bundle)

    preview = preview_restore(tmp_path / "fresh.db", bundle)
    assert preview["target_empty"] is True
    assert preview["would_create"]["source_documents"] == 1
    assert preview["would_create"]["reader_structure_decisions"] == 0
    assert preview["would_create"]["uploads"] == 1
    assert preview["has_investigation"] is True
    assert preview["wbs_version"] == "1.0"


def test_restore_refuses_nonempty_workspace_without_overwrite(tmp_path: Path):
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    _seed(src)
    bundle = tmp_path / "bundle"
    _export(src, bundle)

    # Target already has content.
    dst = tmp_path / "dst" / "workspace.db"
    dst.parent.mkdir(parents=True)
    _seed(dst)

    with pytest.raises(RestoreError):
        restore_workspace(dst, bundle)


def test_preview_flags_nonempty_target(tmp_path: Path):
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    _seed(src)
    bundle = tmp_path / "bundle"
    _export(src, bundle)
    dst = tmp_path / "dst" / "workspace.db"
    dst.parent.mkdir(parents=True)
    _seed(dst)

    assert preview_restore(dst, bundle)["target_empty"] is False


def test_restore_accepts_older_bundle_without_reader_structure_decisions(
    tmp_path: Path,
):
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    _seed(src)
    bundle = tmp_path / "bundle"
    _export(src, bundle)
    (bundle / "governance" / "reader_structure_decisions.json").unlink()
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"] = [
        item for item in manifest["files"]
        if item["path"] != "governance/reader_structure_decisions.json"
    ]
    manifest["counts"].pop("reader_structure_decisions", None)
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    )

    dst = tmp_path / "dst" / "workspace.db"
    dst.parent.mkdir(parents=True)
    result = restore_workspace(dst, bundle)

    assert result["restored"]["reader_structure_decisions"] == 0
    assert _rowdicts(dst, "SELECT * FROM reader_structure_decisions") == []


def test_restore_fails_closed_for_malformed_reader_structure_governance(
    tmp_path: Path,
):
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    _seed(src)
    bundle = tmp_path / "bundle"
    _export(src, bundle)
    governance_file = bundle / "governance" / "reader_structure_decisions.json"
    governance_file.write_text(json.dumps([{"id": "not-a-valid-decision"}]))

    dst = tmp_path / "dst" / "workspace.db"
    dst.parent.mkdir(parents=True)
    with pytest.raises(RestoreError):
        restore_workspace(dst, bundle)
    assert not dst.exists()


def test_restore_fails_closed_for_invalid_reader_structure_snapshot(
    tmp_path: Path,
):
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    doc_id = _seed(src)
    bundle = tmp_path / "bundle"
    _export(src, bundle)
    decision = _reader_structure_decision(doc_id)
    decision["candidate_snapshot"] = "{}"
    governance_file = bundle / "governance" / "reader_structure_decisions.json"
    governance_file.write_text(
        json.dumps([decision], sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    )

    dst = tmp_path / "dst" / "workspace.db"
    dst.parent.mkdir(parents=True)
    with pytest.raises(RestoreError):
        restore_workspace(dst, bundle)
    assert not dst.exists()


def test_restore_fails_closed_for_duplicate_conflicting_structure_decision_id(
    tmp_path: Path,
):
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    doc_id = _seed(src)
    bundle = tmp_path / "bundle"
    _export(src, bundle)
    first = _reader_structure_decision(doc_id)
    second = dict(first)
    second["candidate_snapshot"] = first["candidate_snapshot"].replace(
        "heading_shape",
        "different_shape",
    )
    governance_file = bundle / "governance" / "reader_structure_decisions.json"
    governance_file.write_text(
        json.dumps([first, second], sort_keys=True, indent=2, ensure_ascii=False)
        + "\n"
    )

    dst = tmp_path / "dst" / "workspace.db"
    dst.parent.mkdir(parents=True)
    with pytest.raises(RestoreError):
        restore_workspace(dst, bundle)
    assert not dst.exists()


def test_restore_fails_closed_for_broken_structure_supersession(
    tmp_path: Path,
):
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    doc_id = _seed(src)
    bundle = tmp_path / "bundle"
    _export(src, bundle)
    decision = _reader_structure_decision(
        doc_id,
        supersedes_decision_id="missing-decision",
    )
    governance_file = bundle / "governance" / "reader_structure_decisions.json"
    governance_file.write_text(
        json.dumps([decision], sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    )

    dst = tmp_path / "dst" / "workspace.db"
    dst.parent.mkdir(parents=True)
    with pytest.raises(RestoreError):
        restore_workspace(dst, bundle)
    assert not dst.exists()
