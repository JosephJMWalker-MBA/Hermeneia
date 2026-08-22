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

from hermeneia.perspective_identity import frame_v2_row_from_draft
from hermeneia.storage.sqlite import SQLiteStore
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

    store = SQLiteStore(db_path)
    root, _ = frame_v2_row_from_draft(
        {
            "label": "Institutional Trust Reader",
            "purpose": "Examine trust.",
            "questions": ["Who trusts whom?"],
            "challenges": ["Challenge unsupported legitimacy."],
            "limitations": ["May overemphasize institutions."],
        },
        declared_by="Primary Human Steward",
        declared_date="2026-08-22T12:00:00+00:00",
    )
    successor, _ = frame_v2_row_from_draft(
        {
            "label": "Institutional Trust Reader",
            "purpose": "Examine institutional trust with refined attention.",
            "questions": ["Who trusts whom?"],
            "challenges": ["Challenge unsupported legitimacy."],
            "limitations": ["May overemphasize institutions."],
        },
        declared_by="Primary Human Steward",
        declared_date="2026-08-22T12:05:00+00:00",
        predecessor_perspective_id=root["id"],
    )
    store.insert_frame_perspective(root)
    store.insert_perspective_revision(
        root["id"],
        successor,
        "Refined semantic scope.",
        "2026-08-22T12:05:00+00:00",
    )
    store.close()

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
        "SELECT * FROM perspectives ORDER BY identity_scheme, name, created_at, id",
        "SELECT * FROM supersession_relations ORDER BY old_id, new_id, reason, ratified_at",
        "SELECT * FROM investigation_log ORDER BY id",
        "SELECT thesis, purpose, lenses, reconsider, created_at FROM workspace_investigation",
    ):
        assert _rowdicts(src, sql) == _rowdicts(dst, sql), sql


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
        "study/highlights.json",
        "study/perspectives.json",
        "study/perspective_supersessions.json",
        "study/field_notes.json",
        "investigation.json",
    ):
        assert (b1 / rel).read_bytes() == (b2 / rel).read_bytes(), rel


def test_wbs_10_without_perspectives_restores_as_before(tmp_path: Path):
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    _seed(src)
    bundle = tmp_path / "bundle"
    _export(src, bundle)
    (bundle / "study" / "perspectives.json").unlink()
    (bundle / "study" / "perspective_supersessions.json").unlink()
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["wbs_version"] = "1.0"
    manifest["files"] = [
        entry for entry in manifest["files"]
        if entry["path"] not in {"study/perspectives.json", "study/perspective_supersessions.json"}
    ]
    manifest["counts"].pop("perspectives", None)
    manifest["counts"].pop("perspective_supersessions", None)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n")

    dst = tmp_path / "dst" / "workspace.db"
    dst.parent.mkdir(parents=True)
    result = restore_workspace(dst, bundle)

    assert result["restored"]["source_documents"] == 1
    assert result["restored"]["reader_highlights"] == 1
    assert result["restored"]["perspectives"] == 0
    assert result["restored"]["perspective_supersessions"] == 0
    store = SQLiteStore(dst)
    try:
        assert store.perspective_count() == 0
        assert store._conn.execute("SELECT version FROM schema_version").fetchone()[0] == 17
    finally:
        store.close()


def test_wbs_11_rejects_tampered_frame_v2_identity(tmp_path: Path):
    src = tmp_path / "src" / "workspace.db"
    src.parent.mkdir(parents=True)
    _seed(src)
    bundle = tmp_path / "bundle"
    _export(src, bundle)
    perspectives_path = bundle / "study" / "perspectives.json"
    perspectives = json.loads(perspectives_path.read_text())
    perspectives[0]["definition_fingerprint"] = "sha256:" + "0" * 64
    perspectives_path.write_text(json.dumps(perspectives, sort_keys=True, indent=2, ensure_ascii=False) + "\n")

    dst = tmp_path / "dst" / "workspace.db"
    dst.parent.mkdir(parents=True)
    with pytest.raises(RestoreError, match="fingerprint"):
        restore_workspace(dst, bundle)


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
    assert preview["would_create"]["uploads"] == 1
    assert preview["has_investigation"] is True
    assert preview["wbs_version"] == "1.1"


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
