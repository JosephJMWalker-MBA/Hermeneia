"""Runtime workspace lifecycle helpers.

This module manages filesystem containers for Hermeneia runtime databases. It
does not create a new canonical ontology object: durable workspace identity
remains the existing ``workspace_identity`` row inside each SQLite database.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ..storage.sqlite import SQLiteStore
from .identity import read_workspace_identity, set_workspace_name


DEFAULT_WORKSPACE_ROOT = Path("workspaces")
DEFAULT_LEGACY_DB = Path("build/hermeneia.db")
WORKSPACE_DB_NAME = "hermeneia.db"


class WorkspaceLifecycleError(RuntimeError):
    """Raised when a workspace cannot be created or resolved safely."""


@dataclass(frozen=True)
class WorkspaceRecord:
    """A runtime workspace container discovered on disk."""

    kind: str
    slug: str
    name: str
    db_path: Path
    root_path: Path
    workspace_id: str | None
    created_at: str | None
    updated_at: str | None
    document_count: int


def slugify_workspace_name(name: str) -> str:
    """Return a stable filesystem slug for a human workspace name."""
    cleaned = name.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned).strip("-")
    if not cleaned:
        raise WorkspaceLifecycleError("workspace name must contain letters or numbers")
    return cleaned


def list_workspaces(
    *,
    workspace_root: str | Path = DEFAULT_WORKSPACE_ROOT,
    legacy_db: str | Path = DEFAULT_LEGACY_DB,
) -> list[WorkspaceRecord]:
    """List the legacy DB plus managed workspaces without mutating them."""
    root = Path(workspace_root)
    legacy = Path(legacy_db)
    records: list[WorkspaceRecord] = []

    if legacy.exists():
        records.append(_record_for_db(
            kind="legacy",
            slug="gatsby",
            default_name="Gatsby",
            db_path=legacy,
            root_path=legacy.parent,
        ))

    if root.is_dir():
        for child in sorted(p for p in root.iterdir() if p.is_dir()):
            db_path = child / WORKSPACE_DB_NAME
            if db_path.exists():
                records.append(_record_for_db(
                    kind="managed",
                    slug=child.name,
                    default_name=child.name.replace("-", " ").title(),
                    db_path=db_path,
                    root_path=child,
                ))

    return records


def create_workspace(
    name: str,
    *,
    workspace_root: str | Path = DEFAULT_WORKSPACE_ROOT,
    legacy_db: str | Path = DEFAULT_LEGACY_DB,
) -> WorkspaceRecord:
    """Create an empty isolated managed workspace with durable identity."""
    slug = slugify_workspace_name(name)
    root = Path(workspace_root)
    workspace_dir = root / slug
    if workspace_dir.exists():
        raise WorkspaceLifecycleError(f"workspace already exists: {slug}")

    workspace_dir.mkdir(parents=True)
    (workspace_dir / "uploads").mkdir()
    calibration_path = workspace_dir / "calibration.json"
    calibration_path.write_text(
        json.dumps({"calibration_schema": "1.0", "records": {}}, indent=2) + "\n",
        encoding="utf-8",
    )

    db_path = workspace_dir / WORKSPACE_DB_NAME
    SQLiteStore(db_path).close()
    conn = sqlite3.connect(db_path)
    try:
        set_workspace_name(conn, name.strip())
    finally:
        conn.close()
    return inspect_workspace(slug, workspace_root=root, legacy_db=legacy_db)


def inspect_workspace(
    selector: str,
    *,
    workspace_root: str | Path = DEFAULT_WORKSPACE_ROOT,
    legacy_db: str | Path = DEFAULT_LEGACY_DB,
) -> WorkspaceRecord:
    """Resolve and return one workspace by slug, name, id, or legacy alias."""
    matches = _matching_workspaces(
        selector,
        workspace_root=workspace_root,
        legacy_db=legacy_db,
    )
    if not matches:
        raise WorkspaceLifecycleError(f"workspace not found: {selector}")
    if len(matches) > 1:
        labels = ", ".join(f"{m.name} ({m.slug})" for m in matches)
        raise WorkspaceLifecycleError(f"workspace selector is ambiguous: {labels}")
    return matches[0]


def resolve_workspace_db(
    selector: str,
    *,
    workspace_root: str | Path = DEFAULT_WORKSPACE_ROOT,
    legacy_db: str | Path = DEFAULT_LEGACY_DB,
) -> Path:
    """Resolve a named workspace to the DB path used by ``create_app``."""
    return inspect_workspace(
        selector,
        workspace_root=workspace_root,
        legacy_db=legacy_db,
    ).db_path


def resolve_serve_db(
    *,
    db_arg: str | Path | None = None,
    workspace_selector: str | None = None,
    workspace_root: str | Path = DEFAULT_WORKSPACE_ROOT,
    legacy_db: str | Path = DEFAULT_LEGACY_DB,
) -> Path:
    """Resolve the DB for runtime launch.

    ``--db`` remains the explicit path escape hatch. ``--workspace`` selects a
    managed or legacy workspace. Supplying both is ambiguous and refused.
    """
    if db_arg is not None and workspace_selector:
        raise WorkspaceLifecycleError("use either --db or --workspace, not both")
    if workspace_selector:
        return resolve_workspace_db(
            workspace_selector,
            workspace_root=workspace_root,
            legacy_db=legacy_db,
        )
    return Path(db_arg) if db_arg is not None else Path(legacy_db)


def _matching_workspaces(
    selector: str,
    *,
    workspace_root: str | Path,
    legacy_db: str | Path,
) -> list[WorkspaceRecord]:
    raw = selector.strip()
    normalized = _normalize_selector(raw)
    slug = slugify_workspace_name(raw)
    matches = []
    for record in list_workspaces(workspace_root=workspace_root, legacy_db=legacy_db):
        keys = {
            record.slug,
            _normalize_selector(record.slug),
            _normalize_selector(record.name),
            str(record.db_path),
        }
        if record.workspace_id:
            keys.add(record.workspace_id)
        if record.kind == "legacy":
            keys.update({"legacy", "current", "default", "gatsby"})
        if raw in keys or normalized in keys or slug in keys:
            matches.append(record)
    return matches


def _record_for_db(
    *,
    kind: str,
    slug: str,
    default_name: str,
    db_path: Path,
    root_path: Path,
) -> WorkspaceRecord:
    identity = _read_identity_ro(db_path)
    return WorkspaceRecord(
        kind=kind,
        slug=slug,
        name=(identity or {}).get("workspace_name") or default_name,
        db_path=db_path,
        root_path=root_path,
        workspace_id=(identity or {}).get("workspace_id"),
        created_at=(identity or {}).get("created_at"),
        updated_at=(identity or {}).get("updated_at"),
        document_count=_document_count(db_path),
    )


def _read_identity_ro(db_path: Path) -> dict | None:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        return read_workspace_identity(conn)
    except sqlite3.DatabaseError:
        return None
    finally:
        conn.close()


def _document_count(db_path: Path) -> int:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_documents'"
        ).fetchone()
        if row is None:
            return 0
        return int(conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0])
    except sqlite3.DatabaseError:
        return 0
    finally:
        conn.close()


def _normalize_selector(value: str) -> str:
    return " ".join(value.strip().lower().split())
