"""Workspace Bundle restore / preview (WBS v1, issues #70/#76).

Reconstitute a workspace database from a bundle (the inverse of export.py). v1
restores into a **fresh/empty** workspace only — merging a bundle into an
existing non-empty workspace raises conflict semantics the spec explicitly
defers (§8). ``preview_restore`` reports what a restore would create without
writing anything.

Restored verbatim: the canonical substrate (source_documents, source_extractions,
observations) and the authored records (reader_highlights, investigation_log,
workspace_investigation), plus the uploaded source files. Derived artifacts
(synthesis, lineage, evaluation) are regenerated on demand, never restored as
truth. Reports/governance artifacts are not part of WBS v1.
"""
from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

from ..storage.sqlite import SQLiteStore


# Restore order respects foreign keys:
#   documents → extractions → observations → highlights → field notes → investigation
_TABLE_FILES: list[tuple[str, str]] = [
    ("source_documents", "corpus/documents.json"),
    ("source_extractions", "corpus/extractions.json"),
    ("observations", "corpus/observations.json"),
    ("reader_highlights", "study/highlights.json"),
    ("investigation_log", "study/field_notes.json"),
]

# Tables whose presence means the workspace is not empty.
_OCCUPANCY_TABLES = [table for table, _ in _TABLE_FILES] + ["workspace_investigation"]


class RestoreError(RuntimeError):
    """Raised when a bundle cannot be safely restored."""


def find_bundle_root(extracted: str | Path) -> Path:
    """Locate the directory holding manifest.json inside an extracted bundle.

    Accepts either a bundle extracted at the top level or wrapped in a single
    ``workspace/`` directory (as the download .zip produces).
    """
    extracted = Path(extracted)
    if (extracted / "manifest.json").is_file():
        return extracted
    subdirs = [
        p for p in extracted.iterdir()
        if p.is_dir() and (p / "manifest.json").is_file()
    ]
    if len(subdirs) == 1:
        return subdirs[0]
    raise RestoreError("no manifest.json found in the uploaded bundle")


def safe_extract_zip(zip_bytes: bytes, dest: str | Path) -> Path:
    """Extract a bundle .zip into ``dest``, guarding against path traversal.

    Returns the located bundle root. Raises RestoreError for a malformed or
    unsafe archive.
    """
    dest = Path(dest).resolve()
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            for member in archive.namelist():
                target = (dest / member).resolve()
                if dest not in target.parents and target != dest:
                    raise RestoreError("unsafe path in bundle zip")
            archive.extractall(dest)
    except zipfile.BadZipFile as exc:
        raise RestoreError(f"not a valid .zip bundle: {exc}") from exc
    return find_bundle_root(dest)


def read_bundle(bundle_dir: str | Path) -> dict[str, Any]:
    """Load a bundle directory into memory (manifest + JSON files + upload paths)."""
    root = Path(bundle_dir)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise RestoreError(f"no manifest.json in {root}")
    manifest = json.loads(manifest_path.read_text())

    def _load(rel: str) -> Any:
        path = root / rel
        return json.loads(path.read_text()) if path.is_file() else None

    tables = {table: (_load(rel) or []) for table, rel in _TABLE_FILES}
    investigation = _load("investigation.json")
    uploads_dir = root / "corpus" / "uploads"
    uploads = sorted(
        (p for p in uploads_dir.iterdir() if p.is_file()),
        key=lambda p: p.name,
    ) if uploads_dir.is_dir() else []

    return {
        "manifest": manifest,
        "tables": tables,
        "investigation": investigation,
        "uploads": uploads,
    }


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _workspace_is_empty(conn: sqlite3.Connection) -> bool:
    for table in _OCCUPANCY_TABLES:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue
        if conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
            return False
    return True


def preview_restore(db_path: str | Path, bundle_dir: str | Path) -> dict[str, Any]:
    """Report what a restore would create, without writing anything."""
    bundle = read_bundle(bundle_dir)
    db_path = Path(db_path)
    target_empty = True
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        try:
            target_empty = _workspace_is_empty(conn)
        finally:
            conn.close()
    counts = {table: len(rows) for table, rows in bundle["tables"].items()}
    counts["uploads"] = len(bundle["uploads"])
    return {
        "wbs_version": bundle["manifest"].get("wbs_version"),
        "workspace_id": bundle["manifest"].get("workspace_id"),
        "target_empty": target_empty,
        "would_create": counts,
        "has_investigation": bundle["investigation"] is not None,
    }


def restore_workspace(
    db_path: str | Path,
    bundle_dir: str | Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Restore a bundle into a fresh workspace database.

    Refuses a non-empty target unless ``overwrite=True`` (which the caller must
    set deliberately — v1 has no merge). Returns per-table restored counts.
    """
    db_path = Path(db_path)
    bundle = read_bundle(bundle_dir)

    # Ensure schema exists (creates the DB and all tables if absent).
    SQLiteStore(db_path).close()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if not overwrite and not _workspace_is_empty(conn):
            raise RestoreError(
                "target workspace is not empty; refusing to restore (WBS v1 has "
                "no merge). Pass overwrite=True to restore into a fresh database."
            )

        restored: dict[str, int] = {}
        # Insert in FK order; disable FK enforcement during the bulk load so a
        # partially-covered bundle cannot half-fail mid-restore.
        conn.execute("PRAGMA foreign_keys=OFF")
        for table, _rel in _TABLE_FILES:
            columns = _table_columns(conn, table)
            rows = bundle["tables"][table]
            restored[table] = _insert_rows(conn, table, rows, columns)

        investigation = bundle["investigation"]
        if investigation is not None:
            _restore_investigation(conn, investigation)
            restored["workspace_investigation"] = 1
        conn.commit()
    finally:
        conn.close()

    _restore_uploads(db_path, bundle["uploads"])
    return {"restored": restored, "uploads": len(bundle["uploads"])}


def _insert_rows(
    conn: sqlite3.Connection,
    table: str,
    rows: list[dict],
    columns: set[str],
) -> int:
    count = 0
    for row in rows:
        # Keep only real columns (export may carry joined extras, e.g. a field
        # note's original_filename, which is not an investigation_log column).
        cols = [c for c in row.keys() if c in columns]
        if not cols:
            continue
        placeholders = ",".join("?" for _ in cols)
        conn.execute(
            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
            [row[c] for c in cols],
        )
        count += 1
    return count


def _restore_investigation(conn: sqlite3.Connection, investigation: dict) -> None:
    lenses = investigation.get("lenses")
    conn.execute(
        """INSERT INTO workspace_investigation
             (id, thesis, purpose, lenses, reconsider, created_at, updated_at)
           VALUES ('current', ?, ?, ?, ?, ?, ?)""",
        (
            investigation.get("thesis"),
            investigation.get("purpose"),
            json.dumps(lenses if isinstance(lenses, list) else []),
            investigation.get("reconsider"),
            investigation.get("created_at"),
            investigation.get("updated_at") or investigation.get("created_at"),
        ),
    )


def _restore_uploads(db_path: Path, uploads: list[Path]) -> None:
    if not uploads:
        return
    uploads_dir = db_path.parent / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    for src in uploads:
        (uploads_dir / src.name).write_bytes(src.read_bytes())
