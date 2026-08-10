"""Workspace Bundle restore / preview (WBS v1, issues #70/#76).

Reconstitute a workspace database from a bundle (the inverse of export.py). v1
restores into a **fresh/empty** workspace only — merging a bundle into an
existing non-empty workspace raises conflict semantics the spec explicitly
defers (§8). ``preview_restore`` reports what a restore would create without
writing anything.

Restored verbatim: the canonical substrate (source_documents, source_extractions,
observations) and the authored records (reader_highlights, investigation_log,
workspace_investigation, reader_structure_decisions), plus the uploaded source
files. Derived artifacts (synthesis, lineage, evaluation) are regenerated on
demand, never restored as truth. Recomputable Reader structure candidates are
not restored; steward decisions carry the historical candidate snapshots they
judged.
"""
from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

from ..storage.sqlite import SQLiteStore
from ..web.reader_structure import (
    make_structure_candidate_id,
    structure_evidence_fingerprint,
)
from ..web.reader_structure_stewardship import (
    VALID_STRUCTURE_VERDICTS,
    make_reader_structure_decision_id,
)


# Restore order respects foreign keys:
#   documents → extractions → observations → structure decisions → highlights
#   → field notes → investigation
_TABLE_FILES: list[tuple[str, str]] = [
    ("source_documents", "corpus/documents.json"),
    ("source_extractions", "corpus/extractions.json"),
    ("observations", "corpus/observations.json"),
    ("reader_structure_decisions", "governance/reader_structure_decisions.json"),
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
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise RestoreError(f"malformed JSON in {rel}: {exc}") from exc

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
    _validate_reader_structure_decisions(bundle["tables"])
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
    _validate_reader_structure_decisions(bundle["tables"])

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


def _validate_reader_structure_decisions(
    tables: dict[str, Any],
) -> None:
    rows = tables.get("reader_structure_decisions", [])
    if rows is None:
        tables["reader_structure_decisions"] = []
        return
    if not isinstance(rows, list):
        raise RestoreError(
            "governance/reader_structure_decisions.json must contain a JSON list"
        )
    if not rows:
        return

    document_ids = {
        str(row.get("id") or "")
        for row in tables.get("source_documents", [])
        if isinstance(row, dict)
    }
    extractions = {
        str(row.get("id") or ""): row
        for row in tables.get("source_extractions", [])
        if isinstance(row, dict)
    }
    by_id: dict[str, dict[str, Any]] = {}
    canonical_seen: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RestoreError("reader_structure_decisions entries must be objects")
        decision_id = _required_text(row, "id")
        if decision_id in canonical_seen:
            canonical = json.dumps(row, sort_keys=True, ensure_ascii=False)
            if canonical_seen[decision_id] != canonical:
                raise RestoreError(
                    "duplicate conflicting deterministic reader structure decision id"
                )
            raise RestoreError("duplicate reader structure decision id")
        canonical_seen[decision_id] = json.dumps(row, sort_keys=True, ensure_ascii=False)
        by_id[decision_id] = row

        candidate_id = _required_text(row, "candidate_id")
        document_id = _required_text(row, "document_id")
        if document_id not in document_ids:
            raise RestoreError("reader structure decision references absent document")
        verdict = _required_text(row, "verdict")
        if verdict not in VALID_STRUCTURE_VERDICTS:
            raise RestoreError("reader structure decision verdict is invalid")
        rationale = _required_text(row, "rationale")
        steward_id = _required_text(row, "steward_id")
        decided_at = _required_text(row, "decided_at")
        _required_text(row, "created_at")
        inference_version = _required_text(row, "candidate_inference_version")
        supersedes = _optional_text(row, "supersedes_decision_id")
        expected_id = make_reader_structure_decision_id(
            candidate_id=candidate_id,
            verdict=verdict,
            rationale=rationale,
            steward_id=steward_id,
            decided_at=decided_at,
            supersedes_decision_id=supersedes,
        )
        if expected_id != decision_id:
            raise RestoreError(
                "reader structure decision id does not match deterministic fields"
            )

        snapshot = _candidate_snapshot(row)
        _validate_candidate_snapshot(
            row=row,
            snapshot=snapshot,
            candidate_id=candidate_id,
            document_id=document_id,
            inference_version=inference_version,
            extractions=extractions,
        )

    _validate_reader_structure_supersessions(by_id)
    tables["reader_structure_decisions"] = _topological_decision_order(rows)


def _candidate_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    snapshot_raw = row.get("candidate_snapshot")
    if not isinstance(snapshot_raw, str):
        raise RestoreError("reader structure decision candidate_snapshot must be JSON text")
    try:
        snapshot = json.loads(snapshot_raw)
    except json.JSONDecodeError as exc:
        raise RestoreError("reader structure decision candidate_snapshot is malformed") from exc
    if not isinstance(snapshot, dict):
        raise RestoreError("reader structure decision candidate_snapshot must be an object")
    return snapshot


def _validate_candidate_snapshot(
    *,
    row: dict[str, Any],
    snapshot: dict[str, Any],
    candidate_id: str,
    document_id: str,
    inference_version: str,
    extractions: dict[str, dict[str, Any]],
) -> None:
    if str(snapshot.get("candidate_id") or "") != candidate_id:
        raise RestoreError("reader structure decision snapshot candidate_id mismatch")
    if str(snapshot.get("document_id") or "") != document_id:
        raise RestoreError("reader structure decision snapshot document_id mismatch")
    if str(snapshot.get("inference_version") or "") != inference_version:
        raise RestoreError("reader structure decision snapshot inference version mismatch")

    kind = _snapshot_text(snapshot, "kind")
    heading_text = _snapshot_text(snapshot, "heading_text")
    start_locator = _snapshot_text(snapshot, "start_locator")
    contributing_ids = _snapshot_text_list(snapshot, "contributing_extraction_ids")
    contributing_locators = _snapshot_text_list(snapshot, "contributing_locators")
    evidence_blocks = snapshot.get("evidence_blocks")
    if not isinstance(evidence_blocks, list) or not evidence_blocks:
        raise RestoreError("reader structure decision snapshot evidence_blocks invalid")

    block_ids: list[str] = []
    block_locators: list[str] = []
    for block in evidence_blocks:
        if not isinstance(block, dict):
            raise RestoreError("reader structure decision evidence block invalid")
        _snapshot_text(block, "role")
        extraction_id = _snapshot_text(block, "source_extraction_id")
        extraction = extractions.get(extraction_id)
        if extraction is None:
            raise RestoreError("reader structure decision references absent evidence")
        if str(extraction.get("document_id") or "") != document_id:
            raise RestoreError("reader structure decision evidence document mismatch")
        source_locator = _snapshot_text(block, "source_locator")
        raw_text = str(block.get("raw_text") if block.get("raw_text") is not None else "")
        if source_locator != str(extraction.get("source_locator") or ""):
            raise RestoreError("reader structure decision evidence locator mismatch")
        if raw_text != str(extraction.get("raw_text") or ""):
            raise RestoreError("reader structure decision evidence text mismatch")
        block_ids.append(extraction_id)
        block_locators.append(source_locator)

    if contributing_ids != block_ids:
        raise RestoreError("reader structure decision contributing evidence mismatch")
    if contributing_locators != block_locators:
        raise RestoreError("reader structure decision contributing locator mismatch")

    evidence_fingerprint = _snapshot_text(snapshot, "evidence_fingerprint")
    if evidence_fingerprint != structure_evidence_fingerprint(evidence_blocks):
        raise RestoreError("reader structure decision evidence fingerprint mismatch")

    expected_candidate_id = make_structure_candidate_id(
        document_id=document_id,
        kind=kind,
        source_locator=start_locator,
        heading_text=heading_text,
        title_text=snapshot.get("title_text"),
        contributing_ids=contributing_ids,
        contributing_locators=contributing_locators,
        evidence_fingerprint=evidence_fingerprint,
        inference_version=inference_version,
    )
    if expected_candidate_id != candidate_id:
        raise RestoreError("reader structure decision candidate_id is not deterministic")

    if row.get("candidate_snapshot") != json.dumps(
        snapshot,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ):
        raise RestoreError("reader structure decision candidate_snapshot is not canonical")


def _validate_reader_structure_supersessions(
    rows_by_id: dict[str, dict[str, Any]],
) -> None:
    supersedes_by_id: dict[str, str] = {}
    for decision_id, row in rows_by_id.items():
        supersedes = _optional_text(row, "supersedes_decision_id")
        if not supersedes:
            continue
        if supersedes == decision_id:
            raise RestoreError("reader structure decision cannot supersede itself")
        prior = rows_by_id.get(supersedes)
        if prior is None:
            raise RestoreError("broken reader structure decision supersession reference")
        if prior.get("candidate_id") != row.get("candidate_id"):
            raise RestoreError("reader structure supersession candidate mismatch")
        if prior.get("document_id") != row.get("document_id"):
            raise RestoreError("reader structure supersession document mismatch")
        supersedes_by_id[decision_id] = supersedes

    for decision_id in supersedes_by_id:
        seen: set[str] = set()
        current: str | None = decision_id
        while current in supersedes_by_id:
            if current in seen:
                raise RestoreError("reader structure decision supersession cycle")
            seen.add(current)
            current = supersedes_by_id.get(current)


def _topological_decision_order(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remaining = {str(row["id"]): row for row in rows}
    ordered: list[dict[str, Any]] = []
    inserted: set[str] = set()
    while remaining:
        progressed = False
        for decision_id, row in list(remaining.items()):
            supersedes = _optional_text(row, "supersedes_decision_id")
            if supersedes and supersedes not in inserted:
                continue
            ordered.append(row)
            inserted.add(decision_id)
            del remaining[decision_id]
            progressed = True
        if not progressed:
            raise RestoreError("reader structure decision supersession cycle")
    return ordered


def _required_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None or not str(value).strip():
        raise RestoreError(f"reader structure decision {key} is required")
    return str(value)


def _optional_text(row: dict[str, Any], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    if not str(value).strip():
        raise RestoreError(f"reader structure decision {key} must not be empty")
    return str(value)


def _snapshot_text(snapshot: dict[str, Any], key: str) -> str:
    value = snapshot.get(key)
    if value is None or not str(value).strip():
        raise RestoreError(f"reader structure snapshot {key} is required")
    return str(value)


def _snapshot_text_list(snapshot: dict[str, Any], key: str) -> list[str]:
    value = snapshot.get(key)
    if not isinstance(value, list) or not value:
        raise RestoreError(f"reader structure snapshot {key} must be a non-empty list")
    result = [str(item) for item in value]
    if any(not item.strip() for item in result):
        raise RestoreError(f"reader structure snapshot {key} contains an empty value")
    return result


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
