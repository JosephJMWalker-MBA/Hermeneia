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

import hashlib
import io
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

from ..perspective_identity import FRAME_V2_SCHEME, validate_frame_v2_row_identity
from ..storage.sqlite import SQLiteStore


# Restore order respects foreign keys:
#   documents → extractions → observations → perspectives → highlights → field notes → investigation
_TABLE_FILES: list[tuple[str, str]] = [
    ("source_documents", "corpus/documents.json"),
    ("source_extractions", "corpus/extractions.json"),
    ("observations", "corpus/observations.json"),
    ("perspectives", "study/perspectives.json"),
    ("reader_highlights", "study/highlights.json"),
    ("investigation_log", "study/field_notes.json"),
]

_PERSPECTIVE_SUPERSESSION_FILE = "study/perspective_supersessions.json"

# Required capabilities this restorer can reconstruct (see export.py).
_PUBLICATION_CAPABILITY = "publication-authoring-v0"
_PUBLICATION_PREFIX = "publication/"
SUPPORTED_CAPABILITIES = frozenset({_PUBLICATION_CAPABILITY})

# Tables whose presence means the workspace is not empty.
_OCCUPANCY_TABLES = [table for table, _ in _TABLE_FILES] + ["workspace_investigation", "publication_works"]


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

    unknown = sorted(set(manifest.get("required_capabilities") or []) - SUPPORTED_CAPABILITIES)
    if unknown:
        raise RestoreError(
            "bundle requires capabilities this Hermeneia cannot restore: " + ", ".join(unknown)
        )
    tables = {table: (_load(rel) or []) for table, rel in _TABLE_FILES}
    perspective_supersessions = _load(_PERSPECTIVE_SUPERSESSION_FILE) or []
    publication = _read_publication_component(root, manifest)
    investigation = _load("investigation.json")
    uploads_dir = root / "corpus" / "uploads"
    uploads = sorted(
        (p for p in uploads_dir.iterdir() if p.is_file()),
        key=lambda p: p.name,
    ) if uploads_dir.is_dir() else []

    return {
        "manifest": manifest,
        "tables": tables,
        "perspective_supersessions": perspective_supersessions,
        "investigation": investigation,
        "uploads": uploads,
        "publication": publication,
    }


def _read_publication_component(root: Path, manifest: dict) -> dict[str, Any] | None:
    """Load and verify the integrated authoring history, or refuse the bundle.

    Every ``publication/`` file must be listed in the manifest with a matching
    SHA-256, no unlisted file may appear, and the authored rows must close over
    their referenced artifacts and accepted-version chain.
    """
    from ..authoring.store import AUTHORING_TABLES

    listed = {
        entry["path"]: entry["sha256"]
        for entry in manifest.get("files") or []
        if str(entry.get("path", "")).startswith(_PUBLICATION_PREFIX)
    }
    pub_dir = root / "publication"
    present = {
        path.relative_to(root).as_posix()
        for path in pub_dir.rglob("*") if path.is_file()
    } if pub_dir.is_dir() else set()
    if not listed and not present:
        if _PUBLICATION_CAPABILITY in (manifest.get("required_capabilities") or []):
            raise RestoreError("bundle declares publication authoring but carries no publication component")
        return None
    if _PUBLICATION_CAPABILITY not in (manifest.get("required_capabilities") or []):
        raise RestoreError("publication component present without its required capability declaration")
    if present - set(listed):
        raise RestoreError("publication component has unlisted files: " + ", ".join(sorted(present - set(listed))))
    for rel, digest in listed.items():
        path = root / rel
        if not path.is_file():
            raise RestoreError(f"publication component file missing: {rel}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RestoreError(f"publication component file failed its hash check: {rel}")

    tables = {}
    for table in AUTHORING_TABLES:
        path = pub_dir / "tables" / f"{table}.json"
        tables[table] = json.loads(path.read_text()) if path.is_file() else []
    files: dict[str, Path] = {}
    for rel in listed:
        if rel.startswith("publication/files/"):
            relpath = rel[len("publication/files/"):]
            parts = Path(relpath).parts
            if Path(relpath).is_absolute() or ".." in parts or len(parts) < 2:
                raise RestoreError(f"unsafe publication artifact path: {rel}")
            files[relpath] = root / rel
    _validate_publication_closure(tables, files)
    return {"tables": tables, "files": files}


def _validate_publication_closure(tables: dict[str, list[dict]], files: dict[str, Path]) -> None:
    works = tables["publication_works"]
    if len(works) != 1:
        raise RestoreError("publication component must contain exactly one attached work")
    work_id = works[0]["id"]
    artifacts = {row["sha256"]: row for row in tables["publication_artifacts"]}
    for digest, row in artifacts.items():
        path = files.get(f"{row['work_id']}/{row['relpath']}")
        if path is None or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RestoreError(f"publication artifact missing or altered: {row['relpath']}")

    def _need(digest: str | None, label: str) -> None:
        if not digest or digest not in artifacts:
            raise RestoreError(f"authoring history references a missing {label} artifact")

    proposals = {row["id"]: row for row in tables["authoring_proposals"]}
    decisions = {row["id"]: row for row in tables["authoring_decisions"]}
    requests = {row["id"]: row for row in tables["authoring_requests"]}
    for decision in decisions.values():
        if decision["proposal_id"] not in proposals:
            raise RestoreError("authoring decision references a missing proposal")
    for request in requests.values():
        if request["decision_id"] not in decisions:
            raise RestoreError("authoring request references a missing decision")
        _need(request["record_artifact_sha256"], "revision record")
    accepted = sorted(
        (row for row in tables["authoring_outcomes"] if row["status"] == "accepted"),
        key=lambda row: row["chain_index"],
    )
    if [row["chain_index"] for row in accepted] != list(range(len(accepted))):
        raise RestoreError("accepted-version chain is not contiguous")
    parent = works[0]["root_version_ref"]
    for row in accepted:
        request = requests.get(row["request_id"])
        if request is None:
            raise RestoreError("accepted outcome references a missing request")
        if request["expected_parent_ref"] != parent:
            raise RestoreError("accepted-version chain does not close over its parents")
        for column, label in (("receipt_artifact_sha256", "receipt"), ("version_artifact_sha256", "version"),
                              ("ledger_artifact_sha256", "ledger"), ("overlay_artifact_sha256", "overlay")):
            _need(row[column], label)
        if row["work_id"] != work_id:
            raise RestoreError("accepted outcome belongs to a different work")
        parent = row["result_version_ref"]
    for proof in tables["authoring_proofs"]:
        if proof["result_artifact_sha256"]:
            _need(proof["result_artifact_sha256"], "proof result")
        if proof["pdf_artifact_sha256"]:
            _need(proof["pdf_artifact_sha256"], "proof PDF")


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
    counts["perspective_supersessions"] = len(bundle["perspective_supersessions"])
    counts["uploads"] = len(bundle["uploads"])
    if bundle["publication"] is not None:
        for table, rows in bundle["publication"]["tables"].items():
            counts[table] = len(rows)
        counts["publication_files"] = len(bundle["publication"]["files"])
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
        conn.execute("BEGIN")
        try:
            for table, _rel in _TABLE_FILES:
                columns = _table_columns(conn, table)
                rows = bundle["tables"][table]
                restored[table] = _insert_rows(conn, table, rows, columns)

            columns = _table_columns(conn, "supersession_relations")
            restored["perspective_supersessions"] = _insert_rows(
                conn,
                "supersession_relations",
                bundle["perspective_supersessions"],
                columns,
            )
            _validate_restored_perspective_graph(conn)

            investigation = bundle["investigation"]
            if investigation is not None:
                _restore_investigation(conn, investigation)
                restored["workspace_investigation"] = 1

            publication = bundle["publication"]
            if publication is not None:
                from ..authoring.store import AUTHORING_TABLES

                for table in AUTHORING_TABLES:
                    restored[table] = _insert_rows(
                        conn, table, publication["tables"][table], _table_columns(conn, table)
                    )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise RestoreError(str(exc)) from exc
        except Exception:
            conn.rollback()
            raise
    finally:
        try:
            conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error:
            pass
        conn.close()

    _restore_uploads(db_path, bundle["uploads"])
    publication_files = 0
    if bundle["publication"] is not None:
        publication_root = db_path.parent / "publication"
        for relpath, src in sorted(bundle["publication"]["files"].items()):
            dest = publication_root / relpath
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())
            publication_files += 1
    return {"restored": restored, "uploads": len(bundle["uploads"]), "publication_files": publication_files}


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


def _validate_restored_perspective_graph(conn: sqlite3.Connection) -> None:
    rows = [
        dict(row)
        for row in conn.execute("SELECT * FROM perspectives WHERE identity_scheme = ?", (FRAME_V2_SCHEME,))
    ]
    for row in rows:
        incoming = [
            dict(item)
            for item in conn.execute(
                """
                SELECT sr.*
                FROM supersession_relations sr
                JOIN perspectives old_p ON old_p.id = sr.old_id
                WHERE sr.new_id = ?
                ORDER BY sr.ratified_at, sr.old_id
                """,
                (row["id"],),
            )
        ]
        if len(incoming) > 1:
            raise RestoreError("frame-v2 Perspective has more than one predecessor")
        predecessor_id = incoming[0]["old_id"] if incoming else None
        try:
            validate_frame_v2_row_identity(row, predecessor_perspective_id=predecessor_id)
        except ValueError as exc:
            raise RestoreError(str(exc)) from exc
    for row in rows:
        if _perspective_path_exists(conn, row["id"], row["id"], allow_zero_length=False):
            raise RestoreError("Perspective supersession cycle rejected")


def _perspective_path_exists(
    conn: sqlite3.Connection,
    start_id: str,
    target_id: str,
    *,
    allow_zero_length: bool = True,
) -> bool:
    if allow_zero_length and start_id == target_id:
        return True
    row = conn.execute(
        """
        WITH RECURSIVE chain(new_id, path) AS (
            SELECT sr.new_id, '|' || sr.old_id || '|' || sr.new_id || '|'
            FROM supersession_relations sr
            WHERE sr.old_id = ?
              AND sr.old_id IN (SELECT id FROM perspectives)
              AND sr.new_id IN (SELECT id FROM perspectives)
            UNION ALL
            SELECT sr.new_id, chain.path || sr.new_id || '|'
            FROM supersession_relations sr
            JOIN chain ON sr.old_id = chain.new_id
            WHERE sr.old_id IN (SELECT id FROM perspectives)
              AND sr.new_id IN (SELECT id FROM perspectives)
              AND (
                    sr.new_id = ?
                    OR instr(chain.path, '|' || sr.new_id || '|') = 0
                  )
        )
        SELECT 1 FROM chain WHERE new_id = ? LIMIT 1
        """,
        (start_id, target_id, target_id),
    ).fetchone()
    return row is not None


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
