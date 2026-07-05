"""Deterministic Workspace Bundle exporter (WBS v1).

Reads the runtime SQLite database read-only and produces the bundle described in
docs/workspace-bundle-spec.md. Every JSON file is serialized with sorted keys
and stable record ordering so identical database state yields a byte-identical
bundle — the property that makes Git diffs an intellectual history rather than
noise. No secrets, no localStorage, and no `workspace.db` ever enter the bundle.

v1 coverage (the smallest complete representation):
  canonical  — corpus/documents, corpus/extractions, corpus/observations, uploads
  authored   — investigation, study/highlights, field_notes, questions, buckets, rankings
  derived    — synthesis/, lineage/, evaluation/  (marked derived; regenerable)

Deferred to a later exporter PR (additive, no contract change): rendered
reports, critic reports, governance/release artifacts.
"""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

from ..study import compile_synthesis_packet
from ..study.evaluation import (
    build_evaluation_report,
    score_corpus_boundary,
    score_evidence_preservation,
    score_unsupported_claims,
)


WBS_VERSION = "1.0"

# Role of each file on restore (see spec §3).
CANONICAL = "canonical"
AUTHORED = "authored"
DERIVED = "derived"


def _dumps(obj: Any) -> bytes:
    """Deterministic JSON: sorted keys, stable indent, trailing newline."""
    return (
        json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _json_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def _investigation(conn: sqlite3.Connection) -> dict | None:
    if not _table_exists(conn, "workspace_investigation"):
        return None
    row = conn.execute(
        "SELECT thesis, purpose, lenses, reconsider, created_at, updated_at "
        "FROM workspace_investigation WHERE id = 'current'"
    ).fetchone()
    if not row:
        return None
    return {
        "thesis": row["thesis"],
        "purpose": row["purpose"],
        "lenses": _json_list(row["lenses"]),
        "reconsider": row["reconsider"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _study_projections(highlights: list[dict], field_notes: list[dict]) -> dict[str, Any]:
    """questions / buckets / rankings — human-readable projections of highlights."""
    questions = [
        {
            "highlight_id": h["id"],
            "text": h["question_text"],
            "page": h.get("page"),
            "source_locator": h.get("source_locator"),
        }
        for h in highlights
        if (h.get("question_text") or "").strip()
    ]
    questions += [
        {
            "field_note_id": note["id"],
            "text": note["pressing_questions"],
            "page": note.get("page"),
        }
        for note in field_notes
        if (note.get("pressing_questions") or "").strip()
    ]
    questions.sort(key=lambda q: (str(q.get("text") or ""), str(
        q.get("highlight_id") or q.get("field_note_id") or "")))

    theme: dict[str, list[str]] = {}
    evidence: dict[str, list[str]] = {}
    for h in highlights:
        tb = (h.get("theme_bucket") or "").strip()
        if tb:
            theme.setdefault(tb, []).append(h["id"])
        eb = (h.get("evidence_bucket") or "").strip()
        if eb:
            evidence.setdefault(eb, []).append(h["id"])
    buckets = {
        "theme": {name: sorted(ids) for name, ids in sorted(theme.items())},
        "evidence": {name: sorted(ids) for name, ids in sorted(evidence.items())},
    }

    rankings = {
        h["id"]: h["rank"]
        for h in highlights
        if isinstance(h.get("rank"), int) and h["rank"]
    }
    return {"questions": questions, "buckets": buckets, "rankings": rankings}


def _derived(
    conn: sqlite3.Connection,
    *,
    highlights: list[dict],
    documents: list[dict],
    field_notes: list[dict],
    generated_at: str,
    governing_question: str | None,
) -> dict[str, Any]:
    """Compile the deterministic, provider-free derivations (regenerable)."""
    annotations = []
    for h in highlights:
        d = dict(h)
        d["tags"] = _json_list(d.get("tags"))
        annotations.append(d)
    reading_progress = _rows(
        conn,
        "SELECT document_id, pages_read, last_page, completed_at, updated_at "
        "FROM reading_progress ORDER BY document_id",
    )
    packet = compile_synthesis_packet(
        annotations,
        documents=documents,
        field_notes=field_notes,
        reading_progress=reading_progress,
        compiled_at=generated_at,
        governing_question=governing_question,
    )
    verdicts = [
        score_evidence_preservation(packet),
        score_corpus_boundary(packet),
        score_unsupported_claims(packet),
    ]
    report = build_evaluation_report([("study", verdicts)], generated_at=generated_at)
    return {"packet": packet, "lineage": packet["lineage"], "evaluation": report}


def build_bundle_files(
    conn: sqlite3.Connection,
    *,
    generated_at: str,
    workspace_id: str,
    upload_files: list[tuple[str, bytes]] | None = None,
    app_version: str = "",
) -> dict[str, bytes]:
    """Build every bundle file (including manifest) as path → bytes.

    Pure and deterministic: identical inputs (DB state, generated_at,
    workspace_id, uploads) produce byte-identical output. Read-only over the DB.
    """
    # Verbatim so the bundle round-trips losslessly (restore re-inserts these).
    documents = _rows(conn, "SELECT * FROM source_documents ORDER BY id")
    # Packet-shaped view for the derived compile (which reads `filename`).
    packet_documents = [
        {
            "id": d.get("id"),
            "filename": d.get("original_filename"),
            "file_hash": d.get("file_hash"),
            "source_role": d.get("source_role"),
            "total_pages": d.get("total_pages"),
            "excluded_from_analysis": d.get("excluded_from_analysis"),
        }
        for d in documents
    ]
    extractions = _rows(
        conn,
        "SELECT * FROM source_extractions ORDER BY document_id, source_locator, id",
    )
    observations = _rows(conn, "SELECT * FROM observations ORDER BY id")
    highlights = _rows(
        conn, "SELECT * FROM reader_highlights ORDER BY page, created_at, id"
    )
    field_notes = _rows(
        conn,
        "SELECT il.*, sd.original_filename FROM investigation_log il "
        "LEFT JOIN source_documents sd ON sd.id = il.source_document_id "
        "ORDER BY il.created_at, il.id",
    )
    investigation = _investigation(conn)
    projections = _study_projections(highlights, field_notes)
    derived = _derived(
        conn,
        highlights=highlights,
        documents=packet_documents,
        field_notes=field_notes,
        generated_at=generated_at,
        governing_question=(investigation or {}).get("thesis"),
    )

    # path → (role, bytes). Uploads handled below.
    content: dict[str, tuple[str, bytes]] = {
        "investigation.json": (AUTHORED, _dumps(investigation)),
        "corpus/documents.json": (CANONICAL, _dumps(documents)),
        "corpus/extractions.json": (CANONICAL, _dumps(extractions)),
        "corpus/observations.json": (CANONICAL, _dumps(observations)),
        "study/highlights.json": (AUTHORED, _dumps(highlights)),
        "study/field_notes.json": (AUTHORED, _dumps(field_notes)),
        "study/questions.json": (AUTHORED, _dumps(projections["questions"])),
        "study/buckets.json": (AUTHORED, _dumps(projections["buckets"])),
        "study/rankings.json": (AUTHORED, _dumps(projections["rankings"])),
        "synthesis/packet-study.json": (DERIVED, _dumps(derived["packet"])),
        "lineage/lineage.json": (DERIVED, _dumps(derived["lineage"])),
        "evaluation/report.json": (DERIVED, _dumps(derived["evaluation"])),
    }

    # Uploads: content-hash-named canonical files (the exact source, §5.1).
    for filename, data in sorted(upload_files or []):
        digest = hashlib.sha256(data).hexdigest()
        suffix = Path(filename).suffix
        content[f"corpus/uploads/{digest}{suffix}"] = (CANONICAL, data)

    # Manifest last — it describes every other file.
    files_manifest = [
        {"path": path, "role": role, "sha256": hashlib.sha256(data).hexdigest()}
        for path, (role, data) in sorted(content.items())
    ]
    manifest = {
        "wbs_version": WBS_VERSION,
        "workspace_id": workspace_id,
        "created_at": generated_at,
        "updated_at": generated_at,
        "generator": {"tool": "hermeneia", "version": app_version},
        "files": files_manifest,
        "counts": {
            "documents": len(documents),
            "extractions": len(extractions),
            "observations": len(observations),
            "highlights": len(highlights),
            "field_notes": len(field_notes),
        },
    }

    out: dict[str, bytes] = {path: data for path, (_role, data) in content.items()}
    out["manifest.json"] = _dumps(manifest)
    return out


def _read_upload_files(db_path: Path) -> list[tuple[str, bytes]]:
    uploads_dir = Path(db_path).parent / "uploads"
    files: list[tuple[str, bytes]] = []
    if uploads_dir.is_dir():
        for f in sorted(uploads_dir.iterdir()):
            if f.is_file():
                files.append((f.name, f.read_bytes()))
    return files


def build_workspace_zip(
    db_path: str | Path,
    *,
    generated_at: str,
    workspace_id: str | None = None,
    app_version: str = "",
) -> bytes:
    """Build the workspace bundle as a deterministic in-memory .zip.

    The archive is written with a fixed entry timestamp and sorted paths so
    identical inputs produce byte-identical zip bytes — no temp files, no DB
    mutation. This is what the Export Workspace download returns.
    """
    db_path = Path(db_path)
    if workspace_id is None:
        workspace_id = _default_workspace_id(db_path)
    conn = _connect_ro(db_path)
    try:
        files = build_bundle_files(
            conn,
            generated_at=generated_at,
            workspace_id=workspace_id,
            upload_files=_read_upload_files(db_path),
            app_version=app_version,
        )
    finally:
        conn.close()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            info = zipfile.ZipInfo(f"workspace/{path}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[path])
    return buffer.getvalue()


def _default_workspace_id(db_path: Path) -> str:
    """Deterministic workspace id from the canonical corpus (stable per workspace)."""
    conn = _connect_ro(db_path)
    try:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM source_documents ORDER BY id")]
    finally:
        conn.close()
    seed = "|".join(ids) or "empty"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def export_workspace_bundle(
    db_path: str | Path,
    out_dir: str | Path,
    *,
    generated_at: str,
    workspace_id: str | None = None,
    app_version: str = "",
) -> dict[str, Any]:
    """Export the workspace to a bundle directory. Read-only over the DB.

    Returns the parsed manifest. ``generated_at`` and ``workspace_id`` are
    explicit so identical state yields a byte-identical bundle.
    """
    db_path = Path(db_path)
    out_dir = Path(out_dir)
    if workspace_id is None:
        workspace_id = _default_workspace_id(db_path)

    uploads_dir = db_path.parent / "uploads"
    upload_files: list[tuple[str, bytes]] = []
    if uploads_dir.is_dir():
        for f in sorted(uploads_dir.iterdir()):
            if f.is_file():
                upload_files.append((f.name, f.read_bytes()))

    conn = _connect_ro(db_path)
    try:
        files = build_bundle_files(
            conn,
            generated_at=generated_at,
            workspace_id=workspace_id,
            upload_files=upload_files,
            app_version=app_version,
        )
    finally:
        conn.close()

    for rel_path, data in files.items():
        dest = out_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    return json.loads(files["manifest.json"])
