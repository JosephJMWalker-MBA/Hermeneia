"""Workspace Bundle exporter (WBS v1, issues #70/#76).

Exercises the deterministic, read-only DB → bundle export: coverage of the
canonical + authored core, derived files marked derived, determinism, integrity
(sha256), upload content-hash naming, exclusion of secrets/localStorage/db, and
read-only safety over the database.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.workspace import (
    WBS_VERSION,
    build_bundle_files,
    export_workspace_bundle,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed(tmp_path: Path) -> Path:
    """A small but complete workspace: a doc, an extraction, a highlight, a
    field note, an investigation, and an uploaded file."""
    db_path = tmp_path / "workspace.db"
    SQLiteStore(db_path).close()
    doc_id = "a" * 64
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO source_documents
           (id, original_filename, file_hash, total_pages, registered_at,
            compiler_version, source_role, excluded_from_analysis)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, "gatsby.pdf", doc_id, 3, _now(), "test", "primary", 0),
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
         "Aspiration made visible.", "Does hope require distance?", "unclear",
         "[]", "saved_highlight", 5, "aspiration", _now(), _now()),
    )
    conn.execute(
        """INSERT INTO investigation_log
           (id, lane, understanding, pressing_questions, source_document_id,
            page, governing_question, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        ("fn-1", "corpus", "Distance sustains desire.", "Can it survive attainment?",
         doc_id, 2, "How does desire depend on distance?", _now()),
    )
    conn.execute(
        """INSERT INTO workspace_investigation
           (id, thesis, purpose, lenses, reconsider, created_at, updated_at)
           VALUES ('current', ?, ?, ?, ?, ?, ?)""",
        ("How does desire depend on distance?", "Trace aspiration.",
         '["aspiration"]', None, _now(), _now()),
    )
    conn.commit()
    conn.close()

    uploads = db_path.parent / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    (uploads / "gatsby_abc.pdf").write_bytes(b"%PDF-1.7 fake gatsby bytes")
    return db_path


def _export(db_path: Path, out: Path) -> dict:
    return export_workspace_bundle(
        db_path, out,
        generated_at="2026-07-04T15:00:00+00:00",
        workspace_id="ws-test",
    )


# ── Coverage ───────────────────────────────────────────────────────────────


def test_export_produces_the_v1_bundle_layout(tmp_path: Path):
    db_path = _seed(tmp_path)
    out = tmp_path / "bundle"
    manifest = _export(db_path, out)

    for rel in (
        "manifest.json",
        "investigation.json",
        "corpus/documents.json",
        "corpus/extractions.json",
        "corpus/observations.json",
        "study/highlights.json",
        "study/field_notes.json",
        "study/questions.json",
        "study/buckets.json",
        "study/rankings.json",
        "synthesis/packet-study.json",
        "lineage/lineage.json",
        "evaluation/report.json",
    ):
        assert (out / rel).is_file(), rel

    assert manifest["wbs_version"] == WBS_VERSION
    assert manifest["counts"]["documents"] == 1
    assert manifest["counts"]["highlights"] == 1


def test_no_workspace_db_or_secrets_or_localstorage_in_bundle(tmp_path: Path):
    db_path = _seed(tmp_path)
    out = tmp_path / "bundle"
    _export(db_path, out)
    paths = [str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()]
    assert not any(p.endswith(".db") for p in paths)
    blob = "\n".join((out / p).read_text(errors="ignore")
                      for p in paths if p.endswith(".json"))
    assert "API_KEY" not in blob
    assert "hermeneia_investigation_v1" not in blob  # no localStorage keys


def test_canonical_and_authored_content_is_verbatim(tmp_path: Path):
    db_path = _seed(tmp_path)
    out = tmp_path / "bundle"
    _export(db_path, out)

    docs = json.loads((out / "corpus/documents.json").read_text())
    assert docs[0]["filename"] == "gatsby.pdf"
    assert docs[0]["excluded"] is False
    inv = json.loads((out / "investigation.json").read_text())
    assert inv["thesis"] == "How does desire depend on distance?"
    assert inv["lenses"] == ["aspiration"]
    hls = json.loads((out / "study/highlights.json").read_text())
    assert hls[0]["id"] == "hl-1"


def test_derived_files_are_marked_derived_in_manifest(tmp_path: Path):
    db_path = _seed(tmp_path)
    out = tmp_path / "bundle"
    manifest = _export(db_path, out)
    role = {f["path"]: f["role"] for f in manifest["files"]}
    assert role["corpus/documents.json"] == "canonical"
    assert role["corpus/extractions.json"] == "canonical"
    assert role["investigation.json"] == "authored"
    assert role["study/highlights.json"] == "authored"
    assert role["synthesis/packet-study.json"] == "derived"
    assert role["lineage/lineage.json"] == "derived"
    assert role["evaluation/report.json"] == "derived"


def test_uploads_are_preserved_and_content_hash_named(tmp_path: Path):
    import hashlib

    db_path = _seed(tmp_path)
    out = tmp_path / "bundle"
    manifest = _export(db_path, out)
    data = b"%PDF-1.7 fake gatsby bytes"
    digest = hashlib.sha256(data).hexdigest()
    upload = out / "corpus" / "uploads" / f"{digest}.pdf"
    assert upload.is_file()
    assert upload.read_bytes() == data
    role = {f["path"]: f["role"] for f in manifest["files"]}
    assert role[f"corpus/uploads/{digest}.pdf"] == "canonical"


# ── Determinism + integrity ────────────────────────────────────────────────


def test_export_is_byte_identical_for_identical_state(tmp_path: Path):
    db_path = _seed(tmp_path)
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    _export(db_path, out_a)
    _export(db_path, out_b)
    files_a = sorted(p.relative_to(out_a) for p in out_a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(out_b) for p in out_b.rglob("*") if p.is_file())
    assert files_a == files_b
    for rel in files_a:
        assert (out_a / rel).read_bytes() == (out_b / rel).read_bytes()


def test_manifest_sha256_matches_file_contents(tmp_path: Path):
    import hashlib

    db_path = _seed(tmp_path)
    out = tmp_path / "bundle"
    manifest = _export(db_path, out)
    for entry in manifest["files"]:
        data = (out / entry["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], entry["path"]


def test_json_files_have_sorted_keys(tmp_path: Path):
    db_path = _seed(tmp_path)
    out = tmp_path / "bundle"
    _export(db_path, out)
    raw = (out / "investigation.json").read_text()
    reserialized = json.dumps(json.loads(raw), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    assert raw == reserialized


# ── Read-only safety ───────────────────────────────────────────────────────


def test_export_does_not_mutate_the_database(tmp_path: Path):
    db_path = _seed(tmp_path)
    before = db_path.read_bytes()
    _export(db_path, tmp_path / "bundle")
    assert db_path.read_bytes() == before


def test_derived_evaluation_report_is_provider_free(tmp_path: Path):
    db_path = _seed(tmp_path)
    out = tmp_path / "bundle"
    _export(db_path, out)
    report = json.loads((out / "evaluation/report.json").read_text())
    assert report["provider_free"] is True
    assert report["canonical_evidence_modified"] is False


def test_empty_workspace_exports_a_valid_bundle(tmp_path: Path):
    db_path = tmp_path / "empty.db"
    SQLiteStore(db_path).close()
    out = tmp_path / "bundle"
    manifest = _export(db_path, out)
    assert manifest["counts"]["documents"] == 0
    assert json.loads((out / "investigation.json").read_text()) is None
