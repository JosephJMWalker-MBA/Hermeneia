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
import os
import shutil
import sqlite3
import uuid
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
_PERSPECTIVE_EXECUTION_FILE = "study/perspective_executions.json"
_PERSPECTIVE_EXECUTION_CAPABILITY = "perspective-retained-execution-v1"
_PERSPECTIVE_EXECUTION_TABLE = "perspective_execution_receipts"
_ACHIEVEMENT_AWARD_FILE = "study/achievement_awards.json"
_ACHIEVEMENT_AWARD_CAPABILITY = "perspective-achievement-awards-v1"
_ACHIEVEMENT_AWARD_TABLE = "achievement_awards"
_ACHIEVEMENT_AWARD_COLUMNS = frozenset({
    "id", "achievement_id", "rule_id", "rule_version", "receipt_json",
})

_ACCEPTED_COMPARISON_FILE = "study/accepted_perspective_comparisons.json"
_ACCEPTED_COMPARISON_CAPABILITY = "accepted-perspective-comparison-v1"
_ACCEPTED_COMPARISON_TABLE = "accepted_perspective_comparisons"
_ACCEPTED_COMPARISON_COLUMNS = frozenset({"id", "candidate_id", "comparison_json"})

# Required capabilities this restorer can reconstruct (see export.py).
_PUBLICATION_CAPABILITY = "publication-authoring-v0"
_PUBLICATION_PREFIX = "publication/"
SUPPORTED_CAPABILITIES = frozenset({
    _PUBLICATION_CAPABILITY, _PERSPECTIVE_EXECUTION_CAPABILITY, _ACHIEVEMENT_AWARD_CAPABILITY,
    _ACCEPTED_COMPARISON_CAPABILITY,
})

# Tables whose presence means the workspace is not empty.
_OCCUPANCY_TABLES = [table for table, _ in _TABLE_FILES] + [
    "workspace_investigation", "publication_works", _PERSPECTIVE_EXECUTION_TABLE,
    _ACHIEVEMENT_AWARD_TABLE, _ACCEPTED_COMPARISON_TABLE,
]


class RestoreError(RuntimeError):
    """Raised when a bundle cannot be safely restored."""


def _unique_json_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


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
    try:
        manifest = json.loads(manifest_path.read_bytes(), object_pairs_hook=_unique_json_keys)
    except (ValueError, UnicodeError) as exc:
        raise RestoreError(f"invalid bundle manifest: {exc}") from exc

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
    perspective_executions, receipt_coverage = _read_perspective_executions(root, manifest)
    achievement_awards, award_coverage = _read_achievement_awards(root, manifest)
    accepted_comparisons, comparison_coverage = _read_accepted_comparisons(root, manifest)
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
        "perspective_executions": perspective_executions,
        "achievement_awards": achievement_awards,
        "accepted_comparisons": accepted_comparisons,
        "coverage": {_PERSPECTIVE_EXECUTION_TABLE: receipt_coverage,
                     _ACHIEVEMENT_AWARD_TABLE: award_coverage,
                     _ACCEPTED_COMPARISON_TABLE: comparison_coverage},
        "investigation": investigation,
        "uploads": uploads,
        "publication": publication,
    }


def _read_perspective_executions(root: Path, manifest: dict) -> tuple[list[dict], dict]:
    """Verify the narrow retained-execution component before any restore write.

    Unsupported older coverage is reported explicitly, never interpreted as
    evidence that no historical Perspective activity occurred.
    """
    declared = _PERSPECTIVE_EXECUTION_CAPABILITY in (manifest.get("required_capabilities") or [])
    listed = [entry for entry in manifest.get("files") or []
              if entry.get("path") == _PERSPECTIVE_EXECUTION_FILE]
    path = root / _PERSPECTIVE_EXECUTION_FILE
    if not declared and not listed and not path.exists():
        return [], {"status": "unsupported", "reason": "Bundle does not cover retained Perspective executions; historical activity is unknown."}
    if not declared:
        raise RestoreError("Perspective execution component lacks its required capability declaration")
    if len(listed) != 1 or listed[0].get("role") != "canonical" or not path.is_file():
        raise RestoreError("Perspective execution component must have one complete canonical manifest entry")
    if root.resolve() not in path.resolve().parents:
        raise RestoreError("Perspective execution component escapes the bundle root")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != listed[0].get("sha256"):
        raise RestoreError("Perspective execution component failed its hash check")
    from ..perspective_execution_receipts import receipt_from_row

    try:
        def unique_keys(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate key in Perspective execution component")
                value[key] = item
            return value

        rows = json.loads(data, object_pairs_hook=unique_keys)
        if not isinstance(rows, list):
            raise ValueError("Perspective execution component must contain a row list")
        ids, run_ids = set(), set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"id", "run_id", "receipt_json"}:
                raise ValueError("malformed Perspective execution row")
            receipt_from_row(row)
            if row["id"] in ids or row["run_id"] in run_ids:
                raise ValueError("duplicate Perspective execution identity")
            ids.add(row["id"])
            run_ids.add(row["run_id"])
        counts = manifest.get("counts")
        if not isinstance(counts, dict):
            raise ValueError("Perspective execution component requires explicit record counts")
        count = counts.get(_PERSPECTIVE_EXECUTION_TABLE)
        if type(count) is not int or count != len(rows):
            raise ValueError("Perspective execution count disagrees with component")
    except (ValueError, TypeError, KeyError) as exc:
        raise RestoreError(str(exc)) from exc
    return rows, {"status": "covered", "extant_records": len(rows),
                  "reason": "Extant retained-receipt category covered; no complete historical activity claim."}


def _read_achievement_awards(root: Path, manifest: dict) -> tuple[list[dict], dict]:
    """Validate the award wire component without accepting or issuing history."""
    declared = _ACHIEVEMENT_AWARD_CAPABILITY in (manifest.get("required_capabilities") or [])
    listed = [entry for entry in manifest.get("files") or []
              if entry.get("path") == _ACHIEVEMENT_AWARD_FILE]
    path = root / _ACHIEVEMENT_AWARD_FILE
    if not declared and not listed and not path.exists():
        return [], {"status": "unsupported",
                    "reason": "Bundle does not cover achievement award history; historical awards are unknown."}
    if not declared:
        raise RestoreError("Achievement award component lacks its required capability declaration")
    if len(listed) != 1 or listed[0].get("role") != "canonical" or not path.is_file():
        raise RestoreError("Achievement award component must have one complete canonical manifest entry")
    if root.resolve() not in path.resolve().parents:
        raise RestoreError("Achievement award component escapes the bundle root")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != listed[0].get("sha256"):
        raise RestoreError("Achievement award component failed its hash check")
    from ..achievement_awards import award_from_row

    try:
        rows = json.loads(data, object_pairs_hook=_unique_json_keys)
        if not isinstance(rows, list):
            raise ValueError("Achievement award component must contain a row list")
        ids, slots = set(), set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != _ACHIEVEMENT_AWARD_COLUMNS:
                raise ValueError("malformed achievement award row")
            award_from_row(row)
            slot = (row["achievement_id"], row["rule_id"], row["rule_version"])
            if row["id"] in ids or slot in slots:
                raise ValueError("duplicate achievement award identity or slot")
            ids.add(row["id"])
            slots.add(slot)
        if [row["id"] for row in rows] != sorted(ids):
            raise ValueError("Achievement award component must use ASCII identity order")
        counts = manifest.get("counts")
        if not isinstance(counts, dict):
            raise ValueError("Achievement award component requires explicit record counts")
        count = counts.get(_ACHIEVEMENT_AWARD_TABLE)
        if type(count) is not int or count != len(rows):
            raise ValueError("Achievement award count disagrees with component")
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise RestoreError(str(exc)) from exc
    return rows, {"status": "covered", "extant_records": len(rows),
                  "reason": "Extant award category covered; no complete historical award claim."}


def _read_accepted_comparisons(root: Path, manifest: dict) -> tuple[list[dict], dict]:
    """Validate the accepted-comparison component without accepting anything anew."""
    declared = _ACCEPTED_COMPARISON_CAPABILITY in (manifest.get("required_capabilities") or [])
    listed = [entry for entry in manifest.get("files") or []
              if entry.get("path") == _ACCEPTED_COMPARISON_FILE]
    path = root / _ACCEPTED_COMPARISON_FILE
    if not declared and not listed and not path.exists():
        return [], {"status": "unsupported",
                    "reason": "Bundle does not cover accepted Perspective comparisons; their history is unknown."}
    if not declared:
        raise RestoreError("Accepted comparison component lacks its required capability declaration")
    if len(listed) != 1 or listed[0].get("role") != "canonical" or not path.is_file():
        raise RestoreError("Accepted comparison component must have one complete canonical manifest entry")
    if root.resolve() not in path.resolve().parents:
        raise RestoreError("Accepted comparison component escapes the bundle root")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != listed[0].get("sha256"):
        raise RestoreError("Accepted comparison component failed its hash check")
    from ..accepted_perspective_comparisons import record_from_row

    try:
        rows = json.loads(data, object_pairs_hook=_unique_json_keys)
        if not isinstance(rows, list):
            raise ValueError("Accepted comparison component must contain a row list")
        ids, candidates = set(), set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != _ACCEPTED_COMPARISON_COLUMNS:
                raise ValueError("malformed accepted comparison row")
            record_from_row(row)
            if row["id"] in ids or (row["candidate_id"] is not None and row["candidate_id"] in candidates):
                raise ValueError("duplicate accepted comparison identity or candidate")
            ids.add(row["id"])
            candidates.add(row["candidate_id"])
        if [row["id"] for row in rows] != sorted(ids):
            raise ValueError("Accepted comparison component must use ASCII identity order")
        counts = manifest.get("counts")
        if not isinstance(counts, dict):
            raise ValueError("Accepted comparison component requires explicit record counts")
        count = counts.get(_ACCEPTED_COMPARISON_TABLE)
        if type(count) is not int or count != len(rows):
            raise ValueError("Accepted comparison count disagrees with component")
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise RestoreError(str(exc)) from exc
    return rows, {"status": "covered", "extant_records": len(rows),
                  "reason": "Extant accepted-comparison category covered; no complete historical claim."}


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


def _refuse_occupied_target(conn: sqlite3.Connection, *, award_coverage: bool, overwrite: bool) -> None:
    award_table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_ACHIEVEMENT_AWARD_TABLE,),
    ).fetchone() is not None
    award_target_occupied = award_table_exists and conn.execute(
        f"SELECT 1 FROM {_ACHIEVEMENT_AWARD_TABLE} LIMIT 1"
    ).fetchone() is not None
    if not _workspace_is_empty(conn) and (not overwrite or award_coverage or award_target_occupied):
        raise RestoreError(
            "target workspace is not empty; refusing to restore (WBS v1 has "
            "no award-history merge or overwrite). Restore into a fresh database."
        )


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
    if bundle["coverage"][_PERSPECTIVE_EXECUTION_TABLE]["status"] == "covered":
        counts[_PERSPECTIVE_EXECUTION_TABLE] = len(bundle["perspective_executions"])
    if bundle["coverage"][_ACHIEVEMENT_AWARD_TABLE]["status"] == "covered":
        counts[_ACHIEVEMENT_AWARD_TABLE] = len(bundle["achievement_awards"])
    if bundle["coverage"][_ACCEPTED_COMPARISON_TABLE]["status"] == "covered":
        counts[_ACCEPTED_COMPARISON_TABLE] = len(bundle["accepted_comparisons"])
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
        "coverage": bundle["coverage"],
    }


def restore_workspace(
    db_path: str | Path,
    bundle_dir: str | Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Restore a bundle into a fresh workspace database.

    Award history requires a fresh/empty target even with ``overwrite=True``;
    that legacy option cannot merge, replace or ignore an immutable award slot.
    Returns per-table restored counts.
    """
    db_path = Path(db_path)
    bundle = read_bundle(bundle_dir)
    award_coverage = bundle["coverage"][_ACHIEVEMENT_AWARD_TABLE]["status"] == "covered"

    # A refused immutable-history merge must leave even startup/migration DDL
    # outside the occupied target. Recheck after startup for a concurrent writer.
    if db_path.exists():
        existing = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            _refuse_occupied_target(existing, award_coverage=award_coverage, overwrite=overwrite)
        finally:
            existing.close()

    # Ensure schema exists (creates the DB and all tables if absent).
    SQLiteStore(db_path).close()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    staging: Path | None = None
    installed: list[Path] = []
    try:
        _refuse_occupied_target(conn, award_coverage=award_coverage, overwrite=overwrite)

        # Publication artifacts are staged and hash-verified before any row is
        # inserted, installed before the commit, and discarded on any failure,
        # so accepted authoring rows never become active without their files.
        if bundle["publication"] is not None:
            staging = _stage_publication(db_path, bundle["publication"])

        restored: dict[str, int] = {}
        # Insert in FK order; disable FK enforcement during the bulk load so a
        # partially-covered bundle cannot half-fail mid-restore.
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN IMMEDIATE")
        try:
            # Hold the write reservation during the final fresh-target check;
            # a concurrent insert must not turn restore into an implicit merge.
            _refuse_occupied_target(conn, award_coverage=award_coverage, overwrite=overwrite)
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

            receipt_rows = bundle["perspective_executions"]
            if bundle["coverage"][_PERSPECTIVE_EXECUTION_TABLE]["status"] == "covered":
                from ..perspective_execution_receipts import receipt_from_row, validate_execution_references

                for receipt_row in receipt_rows:
                    try:
                        validate_execution_references(conn, receipt_from_row(receipt_row))
                    except (ValueError, KeyError, TypeError) as exc:
                        raise RestoreError(f"invalid Perspective execution references: {exc}") from exc
                restored[_PERSPECTIVE_EXECUTION_TABLE] = _insert_rows(
                    conn, _PERSPECTIVE_EXECUTION_TABLE, receipt_rows,
                    _table_columns(conn, _PERSPECTIVE_EXECUTION_TABLE),
                )

            if award_coverage:
                from ..achievement_awards import award_from_row, validate_award_references

                award_rows = bundle["achievement_awards"]
                for award_row in award_rows:
                    try:
                        validate_award_references(conn, award_from_row(award_row))
                    except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                        raise RestoreError(f"invalid achievement award references: {exc}") from exc
                # Exact component shape was checked above. No generic column
                # filtering may silently discard an unknown award field.
                if not _ACHIEVEMENT_AWARD_COLUMNS <= _table_columns(conn, _ACHIEVEMENT_AWARD_TABLE):
                    raise RestoreError("target cannot store the complete achievement award row")
                restored[_ACHIEVEMENT_AWARD_TABLE] = _insert_rows(
                    conn, _ACHIEVEMENT_AWARD_TABLE, award_rows, set(_ACHIEVEMENT_AWARD_COLUMNS),
                )

            if bundle["coverage"][_ACCEPTED_COMPARISON_TABLE]["status"] == "covered":
                from ..accepted_perspective_comparisons import record_from_row, validate_record_references

                comparison_rows = bundle["accepted_comparisons"]
                for comparison_row in comparison_rows:
                    try:
                        validate_record_references(conn, record_from_row(comparison_row))
                    except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                        raise RestoreError(f"invalid accepted comparison references: {exc}") from exc
                if not _ACCEPTED_COMPARISON_COLUMNS <= _table_columns(conn, _ACCEPTED_COMPARISON_TABLE):
                    raise RestoreError("target cannot store the complete accepted comparison row")
                restored[_ACCEPTED_COMPARISON_TABLE] = _insert_rows(
                    conn, _ACCEPTED_COMPARISON_TABLE, comparison_rows, set(_ACCEPTED_COMPARISON_COLUMNS),
                )

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
            if staging is not None:
                installed = _install_publication(db_path, staging)
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            _discard_publication(db_path, staging, installed)
            raise RestoreError(str(exc)) from exc
        except Exception:
            conn.rollback()
            _discard_publication(db_path, staging, installed)
            raise
    except RestoreError:
        _discard_publication(db_path, staging, installed)
        raise
    finally:
        try:
            conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error:
            pass
        conn.close()

    if staging is not None:
        shutil.rmtree(staging, ignore_errors=True)
    _restore_uploads(db_path, bundle["uploads"])
    publication_files = len(bundle["publication"]["files"]) if bundle["publication"] is not None else 0
    return {"restored": restored, "uploads": len(bundle["uploads"]),
            "publication_files": publication_files, "coverage": bundle["coverage"]}


def _copy_publication_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)


def _stage_publication(db_path: Path, publication: dict[str, Any]) -> Path:
    """Copy and hash-verify every publication file into a sibling staging area."""
    root = db_path.parent / "publication"
    work_ids = sorted({relpath.split("/", 1)[0] for relpath in publication["files"]})
    for work_id in work_ids:
        if (root / work_id).exists():
            raise RestoreError(f"publication area for {work_id} already exists; refusing to overwrite it")
    staging = db_path.parent / f".publication-restore-{uuid.uuid4().hex}"
    try:
        for relpath, src in sorted(publication["files"].items()):
            dest = staging / relpath
            _copy_publication_file(src, dest)
            if hashlib.sha256(dest.read_bytes()).hexdigest() != hashlib.sha256(src.read_bytes()).hexdigest():
                raise RestoreError(f"staged publication file failed its hash check: {relpath}")
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        raise RestoreError(f"publication component could not be staged: {exc}") from exc
    except RestoreError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return staging


def _install_publication(db_path: Path, staging: Path) -> list[Path]:
    """Move each staged work directory into place; returns what was installed."""
    root = db_path.parent / "publication"
    installed: list[Path] = []
    try:
        root.mkdir(parents=True, exist_ok=True)
        for work_dir in sorted(p for p in staging.iterdir() if p.is_dir()):
            final = root / work_dir.name
            os.replace(work_dir, final)
            installed.append(final)
    except OSError as exc:
        for path in installed:
            shutil.rmtree(path, ignore_errors=True)
        raise RestoreError(f"publication component could not be installed: {exc}") from exc
    return installed


def _discard_publication(db_path: Path, staging: Path | None, installed: list[Path]) -> None:
    """Remove a staged or installed publication component after a failed restore."""
    for path in installed:
        shutil.rmtree(path, ignore_errors=True)
    if staging is not None:
        shutil.rmtree(staging, ignore_errors=True)
    root = db_path.parent / "publication"
    if root.is_dir() and not any(root.iterdir()):
        root.rmdir()


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
